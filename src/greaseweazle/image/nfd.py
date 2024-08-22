# greaseweazle/image/nfd.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from typing import Dict, Tuple, Optional, List

import struct

from greaseweazle import error
from greaseweazle.codec.ibm import ibm
from .image import Image, OptDict

TrackDict = Dict[Tuple[int, int], ibm.IBMTrack_Fixed]


class NFD(Image):

    read_only = True

    def __init__(self, name: str, _fmt):
        self.to_track: TrackDict = dict()
        self.filename = name

    @classmethod
    def from_file(cls, name: str, _fmt, opts: OptDict) -> Image:

        nfd = cls(name, _fmt)
        nfd.apply_r_opts(opts)

        with open(name, 'rb') as f:
            header = struct.unpack('<15sx256sLBB10x', f.read(288))
            file_id, comment_bytes, header_size, write_protect, heads = header
            if file_id == b'T98FDDIMAGE.R1\0':
                raise error.Fatal('NFD: r1 format images not supported')
            if file_id != b'T98FDDIMAGE.R0\0':
                raise error.Fatal('NFD: not a NFD image')
            if heads != 2:
                raise error.Fatal('NFD: heads != 2 not supported')
            comment = comment_bytes.decode('sjis')
            print('NFD: comment:', comment)
            if write_protect != 0:
                print('NFD: disk is write protected')
            for physical_track in range(0, 163):
                secs: List[Tuple[int, int, int, int]] = []
                track = None
                track_mfm = 0
                for _ in range(1, 27):
                    sector_header = struct.unpack('<11B5x', f.read(16))
                    c, h, r, n, mfm, ddam, status, st0, st1, st2, pda = sector_header
                    if c == 0xff:
                        continue
                    if track is None:
                        track_mfm = mfm
                        if mfm != 0:
                            track = ibm.IBMTrack_FixedDef('ibm.mfm')
                            track.rate = 500
                        else:
                            track = ibm.IBMTrack_FixedDef('ibm.fm')
                            track.rate = 250
                        track.rpm = 360
                    else:
                        if track_mfm != mfm:
                            raise error.Fatal(
                                'NFD: mixed FM and MFM tracks not supported')
                    if ddam != 0:
                        raise error.Fatal('NFD: DDAM not supported')
                    if status != 0:
                        raise error.Fatal(
                            f'NFD: Status {status:%02x} not supported')
                    if h not in (0, 1):
                        raise error.Fatal(f'NFD: Invalid head value {h}')
                    if h == 0 and st0 != 0x00:
                        raise error.Fatal(f'NFD: ST0 {st0:%02x} not supported')
                    if h == 1 and st0 != 0x04:
                        raise error.Fatal(f'NFD: ST0 {st0:%02x} not supported')
                    if st1 != 0:
                        raise error.Fatal(f'NFD: ST1 {st1:%02x} not supported')
                    if st2 != 0:
                        raise error.Fatal(f'NFD: ST2 {st2:%02x} not supported')
                    if pda != 0x90:
                        raise error.Fatal(f'NFD: PDA {pda:%02x} not supported')
                    secs.append((c, h, r, n))
                if track is not None:
                    assert track is not None
                    track.secs = len(secs)
                    track.sz = [x[3] for x in secs]
                    track.finalise()
                    t = ibm.IBMTrack_Fixed.from_config(
                        track, physical_track // 2, physical_track % 2,
                        warn_on_oversize=True)
                    for nr, s in enumerate(t.sectors):
                        c, h, r, n = secs[nr]
                        s.crc = s.idam.crc = s.dam.crc = 0
                        s.idam.c, s.idam.h, s.idam.r, s.idam.n = c, h, r, n
                    nfd.to_track[physical_track // 2, physical_track % 2] = t
            f.seek(header_size)
            for _, t in nfd.to_track.items():
                for s in t.sectors:
                    s.dam.data = f.read(128 << s.idam.n)

        return nfd

    def get_track(self, cyl: int, side: int) -> Optional[ibm.IBMTrack_Fixed]:
        if (cyl, side) not in self.to_track:
            return None
        return self.to_track[cyl, side]

# Local variables:
# python-indent: 4
# End:
