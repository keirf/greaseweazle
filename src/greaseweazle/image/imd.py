# greaseweazle/image/imd.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
# 
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from typing import Dict, Tuple, Optional

import datetime, struct

from greaseweazle import __version__
from greaseweazle import error
from greaseweazle.codec.ibm import ibm
from .image import Image

class IMDMode:
    FM_500kbps = 0
    FM_300kbps = 1
    FM_250kbps = 2
    MFM_500kbps = 3
    MFM_300kbps = 4
    MFM_250kbps = 5

class IMD(Image):

    def __init__(self, name: str, noclobber=False):
        self.to_track: Dict[Tuple[int,int],ibm.IBMTrack_Fixed] = dict()
        self.filename = name
        self.noclobber = noclobber


    @classmethod
    def from_file(cls, name: str, _fmt) -> Image:

        with open(name, "rb") as f:
            dat = f.read()

        imd = cls(name)

        # Check and strip the header
        sig, = struct.unpack('4s', dat[:4])
        error.check(sig == b'IMD ', 'Unrecognised IMD file: bad signature')
        for i,x in enumerate(dat):
            if x == 0x1a:
                break
        error.check(x == 0x1a, 'IMD: No comment terminator found')

        i += 1
        while i < len(dat):
            mode, cyl, head, nsec, sec_n = struct.unpack('5B', dat[i:i+5])
            i += 5
            error.check(0 <= sec_n <= 6, 'IMD: Bad sector size %x' % sec_n)
            secsz = 128 << sec_n

            has_cyl_map = (head & 0x80) != 0
            has_head_map = (head & 0x40) != 0
            head &= 0x3f
            error.check(0 <= head <= 1, 'IMD: Bad head value %x' % head)

            if mode == IMDMode.FM_250kbps or mode == IMDMode.FM_300kbps:
                fmt = ibm.IBMTrack_FixedDef('ibm.fm')
                fmt.rpm, fmt.rate = 300, 125
            elif mode == IMDMode.FM_500kbps:
                fmt = ibm.IBMTrack_FixedDef('ibm.fm')
                fmt.rpm, fmt.rate = 300, 250
            elif mode == IMDMode.MFM_250kbps or mode == IMDMode.MFM_300kbps:
                fmt = ibm.IBMTrack_FixedDef('ibm.mfm')
                fmt.rpm, fmt.rate = 300, 250
            elif mode == IMDMode.MFM_500kbps:
                fmt = ibm.IBMTrack_FixedDef('ibm.mfm')
                fmt.rpm, fmt.rate = 300, 500
            else:
                raise error.Fatal('IMD: Unrecognised track mode %x' % mode)

            fmt.secs, fmt.sz = nsec, [sec_n]
            fmt.finalise()
            t = fmt.mk_track(cyl, head)

            rmap = dat[i:i+nsec]
            i += nsec
            if has_cyl_map:
                cmap = dat[i:i+nsec]
                i += nsec
            if has_head_map:
                hmap = dat[i:i+nsec]
                i += nsec

            for nr,s in enumerate(t.sectors):
                s.crc = s.idam.crc = s.dam.crc = 0
                s.idam.r = rmap[nr]
                if has_cyl_map:
                    s.idam.c = cmap[nr]
                if has_head_map:
                    s.idam.h = hmap[nr]
                rec = dat[i]
                i += 1
                error.check(0 <= rec <= 8,
                            'IMD: Unexpected sector code %x' % rec)
                if rec == 0:
                    continue # Data unavailable
                rec -= 1
                if rec&1:
                    s.dam.data = bytes([dat[i]] * secsz)
                    i += 1
                else:
                    s.dam.data = dat[i:i+secsz]
                    i += secsz
                if rec&2:
                    s.dam.mark = ibm.Mark.DDAM

            imd.to_track[cyl,head] = t

        return imd


    @classmethod
    def to_file(cls, name: str, fmt, noclobber: bool) -> Image:
        return cls(name, noclobber=noclobber)


    def get_track(self, cyl: int, side: int) -> Optional[ibm.IBMTrack_Fixed]:
        if (cyl,side) not in self.to_track:
            return None
        return self.to_track[cyl,side]


    def emit_track(self, cyl: int, side: int, track) -> None:
        if isinstance(track, ibm.IBMTrack_Scan):
            track = track.track
        error.check(isinstance(track, ibm.IBMTrack),
                    'IMD: Cannot create T%d.%d: Not IBM.FM nor IBM.MFM'
                    % (cyl, side))
        if not isinstance(track, ibm.IBMTrack_Empty):
            self.to_track[cyl,side] = track


    def get_image(self) -> bytes:

        tdat = bytearray()

        now = datetime.datetime.now()
        sig = ('IMD 1.17: %s\r\nGreaseweazle %s\r\n\x1a'
               % (now.strftime('%d/%m/%Y %H:%M:%S'), __version__))
        tdat += sig.encode()

        for (c,h),t in sorted(self.to_track.items()):
            if t.mode is ibm.Mode.FM:
                if t.clock < 3.0e-6:
                    mode = IMDMode.FM_500kbps # High Rate
                elif t.time_per_rev < 0.185:
                    mode = IMDMode.FM_300kbps # 360 RPM
                else:
                    mode = IMDMode.FM_250kbps # 300 RPM
            else:
                assert t.mode is ibm.Mode.MFM
                if t.clock < 1.5e-6:
                    mode = IMDMode.MFM_500kbps # High Rate
                elif t.time_per_rev < 0.185:
                    mode = IMDMode.MFM_300kbps # 360 RPM
                else:
                    mode = IMDMode.MFM_250kbps # 300 RPM
            cyl, head, nsec, sec_n = c, h, 0, None
            rmap, cmap, hmap = [], [], []
            for s in t.sectors:
                if isinstance(s, ibm.Sector):
                    idam = s.idam
                elif isinstance(s, ibm.IDAM):
                    idam = s
                else:
                    continue
                nsec += 1
                error.check(idam.n == sec_n or sec_n is None,
                            'IMD: Cannot create T%d.%d: Sectors vary in size'
                            % (c,h))
                sec_n = idam.n
                rmap.append(idam.r)
                cmap.append(idam.c)
                hmap.append(idam.h)
                if idam.c != c:
                    head |= 0x80
                if idam.h != h:
                    head |= 0x40
            if sec_n is None:
                sec_n = 0
            secsz = 128 << sec_n
            tdat += struct.pack('5B', mode, cyl, head, nsec, sec_n)
            tdat += bytes(rmap)
            if head & 0x80:
                tdat += bytes(cmap)
            if head & 0x40:
                tdat += bytes(hmap)
            for s in t.sectors:
                if isinstance(s, ibm.IDAM):
                    tdat += bytes([0])
                    continue
                elif not isinstance(s, ibm.Sector):
                    continue
                rec = 0
                if s.dam.data.count(s.dam.data[0]) == secsz:
                    rec |= 1
                if s.dam.mark == ibm.Mark.DDAM:
                    rec |= 2
                if s.dam.crc != 0:
                    rec |= 4
                tdat += bytes([rec+1])
                if rec & 1:
                    tdat += s.dam.data[:1]
                else:
                    tdat += s.dam.data[:]

        return tdat


# Local variables:
# python-indent: 4
# End:
