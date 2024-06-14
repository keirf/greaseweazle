# greaseweazle/image/td0.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
# 
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from typing import Dict, Tuple, Optional

import struct
import crcmod.predefined

from greaseweazle import __version__
from greaseweazle import error
from greaseweazle import optimised
from greaseweazle.codec.ibm import ibm
from .image import Image

crc16 = crcmod.predefined.Crc('crc-16-teledisk')

class TD0(Image):

    read_only = True

    def __init__(self, name: str, _fmt) -> None:
        self.to_track: Dict[Tuple[int,int],ibm.IBMTrack_Fixed] = dict()
        self.filename = name


    def from_bytes(self, dat: bytes) -> None:

        # Check and strip the header
        sig, td_ver, data_rate, stepping, n_sides, crc = struct.unpack(
            '<2s2x2BxBxBH', dat[:12])
        error.check(sig == b'TD' or sig == b'td', 'TD0: bad file signature')
        error.check(crc16.new(dat[:10]).crcValue == crc,
                    'TD0: bad file header crc')
        print('TD0: Teledisk version %d.%d' % (td_ver>>4, td_ver&15))

        if sig == b'td':
            print('TD0: Advanced compression')
            error.check(optimised.enabled,
                        'TD0: Decompression requires optimised C extension')
            dat = dat[:12] + optimised.td0_unpack(dat[12:])

        # data_rate[7] = global FM flag
        global_is_fm = (data_rate >> 7) == 1
        data_rate &= 127

        error.check(data_rate <= 2, 'TD0: bad data rate %d' % data_rate)
        data_rate = [250, 300, 500][data_rate]
        n_sides = 1 if n_sides == 1 else 2

        off = 12

        if stepping & 128:
            crc, dlen, yr, mo, day, hr, minute, sec = struct.unpack(
                '<2H6B', dat[off:off+10])
            error.check(crc16.new(dat[off+2:off+10+dlen]).crcValue == crc,
                        'TD0: bad comment header crc')
            print('TD0: Created %d/%d/%d %d:%d:%d' %
                  (day, mo+1, yr+1900, hr, minute, sec))
            off += 10 + dlen

        while dat[off] != 255:

            n_sec, cyl, head, crc = struct.unpack('4B', dat[off:off+4])
            error.check(crc16.new(dat[off:off+3]).crcValue & 0xff == crc,
                        'TD0: bad track header crc')
            off += 4

            track_is_fm = (head & 128) == 128 or global_is_fm
            head &= 127

            fmt = ibm.IBMTrack_FixedDef(['ibm.mfm','ibm.fm'][track_is_fm])
            fmt.rpm, fmt.rate = 300, data_rate
            if track_is_fm:
                fmt.rate = fmt.rate // 2
            fmt.secs = n_sec

            secs = list()
            for _ in range(n_sec):
                id_c,id_h,id_r,id_n,flags,crc = struct.unpack(
                    '6B', dat[off:off+6])
                fmt.sz.append(id_n)
                if not (flags & 0x30):
                    dlen, enc = struct.unpack('<HB', dat[off+6:off+9])
                    dlen -= 1
                    blk = dat[off+9:off+9+dlen]
                    off += 9 + dlen
                    if enc == 1:
                        o, _blk = 0, bytearray()
                        while o < dlen:
                            c, = struct.unpack('<H', blk[o:o+2])
                            _blk += blk[o+2:o+4] * c
                            o += 4
                        blk = _blk
                    if enc == 2:
                        o, _blk = 0, bytearray()
                        while o < dlen:
                            c, n = blk[o], blk[o+1]
                            o += 2
                            if c == 0:
                                _blk += blk[o:o+n]
                                o += n
                            else:
                                _blk += blk[o:o+c*2] * n
                                o += c*2
                        blk = _blk
                    assert len(blk) == ibm.sec_sz(id_n)
                    error.check(crc16.new(blk).crcValue & 0xff == crc,
                                'TD0: bad sector data crc')
                else:
                    off += 6
                    blk = bytes(ibm.sec_sz(id_n))
                secs.append((id_c,id_h,id_r,id_n,flags,blk))


            fmt.finalise()
            t = fmt.mk_track(cyl, head)

            for nr, s in enumerate(t.sectors):
                id_c,id_h,id_r,id_n,flags,blk = secs[nr]
                s.crc = s.idam.crc = s.dam.crc = 0
                s.idam.c, s.idam.h, s.idam.r = id_c, id_h, id_r
                s.dam.data = blk
                if flags & 4:
                    s.dam.mark = ibm.Mark.DDAM

            self.to_track[cyl, head] = t


    def get_track(self, cyl: int, side: int) -> Optional[ibm.IBMTrack_Fixed]:
        if (cyl,side) not in self.to_track:
            return None
        return self.to_track[cyl,side]


# Local variables:
# python-indent: 4
# End:
