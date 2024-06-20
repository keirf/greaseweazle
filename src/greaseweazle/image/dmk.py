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

import binascii, math, struct
import itertools as it
from bitarray import bitarray

from greaseweazle import __version__
from greaseweazle import error
from greaseweazle.codec.ibm import ibm
from greaseweazle.track import MasterTrack, PLLTrack
from .image import Image

class DMKTrack:

    def __init__(self, data):
        time_per_rev = 0.2
        dlen = len(data)
        if dlen < 8000: dlen *= 2
        if dlen < 11000: time_per_rev *= 5/6
        self.track = MasterTrack(
            bits = bytes(data),
            time_per_rev = time_per_rev)

    def master_track(self):
        return self.track

class DMK(Image):

    read_only = True

    def __init__(self, name: str, _fmt) -> None:
        self.to_track: Dict[Tuple[int,int], DMKTrack] = dict()
        self.filename = name

    def from_bytes(self, dat: bytes) -> None:

        ro, ncyl, tlen, flags = struct.unpack(
            '<2BHB', dat[:5])
        error.check(flags & 0xef == 0,
                    'DMK: Unrecognised flags value 0x%02x' % flags)
        nside = 1 if flags & 0x10 else 2

        o = 16 # skip disk header
        for cyl in range(ncyl):
            for head in range(nside):
                offs = list(map(lambda x: ((x & 0x8000) == 0x8000,
                                           (x & 0x3fff) - 128),
                                filter(lambda x: x != 0,
                                       struct.unpack("<64H", dat[o:o+128]))))
                data = dat[o+128:o+tlen]
                o += tlen
                if not offs:
                    continue
                mfm = offs[0][0]
                if mfm:
                    data = ibm.mfm_encode(ibm.doubler(data))
                else:
                    data = ibm.fm_encode(ibm.doubler(data[::2]))
                data = bytearray(data)
                for i, (_mfm, off) in enumerate(offs):
                    error.check(_mfm == mfm,
                                'DMK: Unsupported mixed-format track')
                    if mfm:
                        idam = off*2-6
                        dam = data.find(b'\x44\xa9' * 3, (off+10)*2)
                        error.check(dam != -1, 'DMK: No MFM DAM sync found')
                        error.check(data[idam:idam+6] == b'\x44\xa9' * 3,
                                    'DMK: Bad MFM IDAM sync')
                        data[idam:idam+6] = b'\x44\x89' * 3
                        data[dam:dam+6] = b'\x44\x89' * 3
                    else:
                        idam = (off + 1) & ~1
                        dam = data.find(b'\xaa\xff', idam+10)
                        if dam == -1 and i+1 == len(offs):
                            dam = data.find(b'\xaa\xff', 0, offs[0][1]-2)
                            print(cyl,head,i+1)
                        error.check(dam != -1, 'DMK: No FM DAM sync found')
                        error.check(data[idam:idam+2] == b'\xff\xfe',
                                    'DMK: Bad FM IDAM sync')
                        data[idam] &= 0xf5
                        data[idam+1] &= 0x7f
                        if dam != -1:
                            dam += 1
                            data[dam] &= 0xf5
                            data[dam+1] &= 0x7f

                self.to_track[cyl,head] = DMKTrack(data)

    def get_track(self, cyl: int, side: int) -> Optional[MasterTrack]:
        if (cyl,side) not in self.to_track:
            return None
        return self.to_track[cyl,side].master_track()

# Local variables:
# python-indent: 4
# End:
