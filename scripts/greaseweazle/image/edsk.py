# greaseweazle/image/edsk.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
# 
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import math, struct
import itertools as it

from greaseweazle import error
from greaseweazle.codec.ibm import mfm
from .image import Image

class EDSK(Image):

    read_only = True
    default_format = 'ibm.mfm'

    clock = 2e-6
    time_per_rev = 0.2

    def __init__(self):
        self.to_track = dict()

    @classmethod
    def from_file(cls, name):

        with open(name, "rb") as f:
            dat = f.read()

        edsk = cls()

        sig, creator, ncyls, nsides, track_sz = struct.unpack(
            '<34s14s2BH', dat[:52])
        if sig[:8] == b'MV - CPC':
            extended = False
        elif sig[:16] == b'EXTENDED CPC DSK':
            extended = True
        else:
            raise error.Fatal('Unrecognised CPC DSK file: bad signature')

        if extended:
            tsizes = list(dat[52:52+ncyls*nsides])
            tsizes = list(map(lambda x: x*256, tsizes))
        else:
            raise error.Fatal('Standard CPC DSK file not yet supported')

        o = 256 # skip disk header and track-size table
        for tsize in tsizes:
            if tsize == 0:
                continue
            sig, cyl, head, sec_sz, nsecs, gap_3, filler = struct.unpack(
                '<12s4x2B2x4B', dat[o:o+24])
            error.check(sig == b'Track-Info\r\n',
                        'EDSK: Missing track header')
            error.check((cyl, head) not in edsk.to_track,
                        'EDSK: Track specified twice')
            while True:
                track = mfm.IBM_MFM_Formatted(cyl, head)
                track.clock = cls().clock
                track.time_per_rev = cls().time_per_rev
                pos = track.gap_4a
                track.iams = [mfm.IAM(pos*16,(pos+4)*16)]
                pos += 4 + track.gap_1
                secs = dat[o+24:o+24+8*nsecs]
                data_pos = o + 256 # skip track header and sector-info table
                while secs:
                    c, h, r, n, stat1, stat2, actual_length = struct.unpack(
                        '<6BH', secs[:8])
                    secs = secs[8:]
                    pos += track.gap_presync
                    idam = mfm.IDAM(pos*16, (pos+10)*16, 0,
                                    c=c, h=h, r=r, n=n)
                    pos += 10 + track.gap_2 + track.gap_presync
                    size = 128 << n
                    error.check(size == actual_length,
                                'EDSK: Weird sector size (copy protection?)')
                    error.check(stat1 == 0 and stat2 == 0,
                                'EDSK: Mangled sector (copy protection?)')
                    sec_data = dat[data_pos:data_pos+size]
                    dam = mfm.DAM(pos*16, (pos+4+size+2)*16, 0,
                                  mark=track.DAM, data=sec_data)
                    track.sectors.append(mfm.Sector(idam, dam))
                    pos += 4 + size + 2 + gap_3
                    data_pos += size
                # Some EDSK images have bogus GAP3 values. If the track is too
                # long to comfortably fit in 300rpm at double density, shrink
                # GAP3 as far as necessary.
                tracklen = int((track.time_per_rev / track.clock) / 16)
                overhang = int(pos - tracklen*0.99)
                if overhang <= 0:
                    break
                new_gap_3 = gap_3 - math.ceil(overhang / nsecs)
                error.check(new_gap_3 >= 0,
                            'EDSK: Track %d.%d is too long '
                            '(%d bits @ GAP3=%d; %d bits @ GAP3=0)'
                            % (cyl, head, pos*16, gap_3, (pos-gap_3*nsecs)*16))
                gap_3 = new_gap_3
            edsk.to_track[cyl,head] = track
            o += tsize

        return edsk


    def get_track(self, cyl, side):
        if (cyl,side) not in self.to_track:
            return None
        return self.to_track[cyl,side].raw_track()


# Local variables:
# python-indent: 4
# End:
