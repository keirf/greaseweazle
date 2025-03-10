# greaseweazle/image/dmk.py
#
# Some of the code here is heavily inspired by Simon Owen's SAMdisk:
# https://simonowen.com/samdisk/
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
# 
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from typing import Dict, Tuple, Optional, List, Union

import struct
import itertools as it
from bitarray import bitarray

from greaseweazle import __version__
from greaseweazle import error
from greaseweazle.codec.ibm import ibm
from greaseweazle.track import MasterTrack, PLLTrack
from .image import Image

class Encoding:

    def __init__(self, len: int, mfm: bool, fm_step: int) -> None:
        self.fm_step = fm_step
        self.mfm = [False] * len
        self.clock = bytearray(len)
        self.cursor = 0
        self.prev_mfm = mfm

    def move_cursor(self, off: int) -> None:
        while self.cursor < off:
            self.mfm[self.cursor] = self.prev_mfm
            self.cursor += 1

    def _off(self, areas, data: bytes, off: int, step: int) -> None:
        for i, v, c in areas:
            min_off = max(off - i*step, 0)
            while off > min_off and data[off-step] == v:
                off -= step
                self.clock[off] = c
        self.move_cursor(off)

    def mfm_off(self, data: bytes, off: int) -> None:
        areas = [(  3, 0xa1, 0x0a), # IDAM A1, Clock 0A -> 4489
                 ( 12, 0x00,    0),
                 (512, 0x4e,    0),
                 (  1, 0xfc,    0),
                 (  3, 0xc2, 0x14), # IAM C2, Clock 14 -> 5224
                 ( 12, 0x00,    0),
                 (512, 0x4e,    0)]
        self._off(areas, data, off, 1)
        self.prev_mfm = True

    def fm_off(self, data: bytes, off: int) -> None:
        areas = [(  6, 0x00,    0),
                 (256, 0xff,    0),
                 (  1, 0xfc, 0xd7), # IAM FC, Clock D7
                 (  6, 0x00,    0)]
        self._off(areas, data, off, self.fm_step)
        self.prev_mfm = False


class DMKTrack:

    def __init__(self, data: bytes) -> None:
        time_per_rev = 0.2
        dlen = (len(data) * 8) // 1000
        if (80 <= dlen <= 85) or (160 <= dlen <= 170):
            time_per_rev *= 5/6
        self.track = MasterTrack(
            bits = bytes(data),
            time_per_rev = time_per_rev)

    def master_track(self) -> MasterTrack:
        return self.track


class DMK(Image):

    read_only = True

    def __init__(self, name: str, _fmt) -> None:
        self.to_track: Dict[Tuple[int,int], DMKTrack] = dict()
        self.filename = name

    def from_bytes(self, dat: bytes) -> None:

        ro, ncyl, tlen, flags = struct.unpack('<2BHB', dat[:5])
        error.check(flags & 0x2f == 0,
                    'DMK: Unrecognised flags value 0x%02x' % flags)
        nside = 1 if flags & 0x10 else 2
        fm_step = 1 if flags & 0xc0 else 2

        o = 16 # skip disk header
        for cyl in range(ncyl):
            for head in range(nside):
                offs = list(map(lambda x: ((x & 0x8000) == 0x8000,
                                           (x & 0x3fff) - 128),
                                filter(lambda x: x != 0,
                                       struct.unpack("<64H", dat[o:o+128]))))
                # DMK Spec: "The IDAM offsets MUST be in ascending order with
                # no unused or bad pointers." We clip at the first
                # non-ascending offset, fixing some buggy DMK image imports
                # (for example, which have 0x80 added to empty offset entries).
                prev = -1
                for i, (_, off) in enumerate(offs):
                    if off <= prev:
                        offs = offs[:i]
                        break
                    prev = off
                data = dat[o+128:o+tlen]
                o += tlen
                if not offs:
                    continue
                encoding = Encoding(len(data), offs[0][0], fm_step)
                for mfm, off in offs:
                    if mfm:
                        encoding.mfm_off(data, off)
                        dam = data[off+8:off+64].find(b'\xa1' * 3)
                        error.check(dam != -1, 'DMK: No MFM DAM sync found')
                        dam += off+8
                        encoding.move_cursor(dam+8)
                        encoding.clock[dam+0] = 0x0a
                        encoding.clock[dam+1] = 0x0a
                        encoding.clock[dam+2] = 0x0a
                    else:
                        # Single density: Step-align the offset
                        step = encoding.fm_step
                        off &= ~(step-1)
                        if data[off] == 0:
                            off += step
                        encoding.fm_off(data, off)
                        encoding.clock[off] = 0xc7
                        for dam in range(off+8*step, off+64*step, step):
                            if (data[dam-step] == 0 and
                                data[dam] & 0xf0 == 0xf0):
                                break
                        encoding.move_cursor(dam+8*step)
                        encoding.clock[dam] = 0xc7

                encoding.move_cursor(len(data))

                enc_data, fm_mask = bytearray(), encoding.fm_step-1
                for i in range(len(data)):
                    if not (mfm := encoding.mfm[i]) and (i & fm_mask) != 0:
                        continue
                    d = ibm.encode_list[data[i]]
                    c = ibm.encode_list[encoding.clock[i]]
                    x = struct.pack('>H', (c<<1)|d)
                    if mfm:
                        enc_data += ibm.mfm_encode(x)
                    else:
                        enc_data += ibm.doubler(ibm.fm_encode(x))

                self.to_track[cyl,head] = DMKTrack(enc_data)

    def get_track(self, cyl: int, side: int) -> Optional[MasterTrack]:
        if (cyl,side) not in self.to_track:
            return None
        return self.to_track[cyl,side].master_track()

# Local variables:
# python-indent: 4
# End:
