# greaseweazle/image/adf.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import struct

from greaseweazle import error
from greaseweazle.track import MasterTrack
from greaseweazle.bitcell import Bitcell
import greaseweazle.codec.amiga.amigados as amigados
from bitarray import bitarray

class ADF:

    default_format = 'amiga.amigados'

    def __init__(self, start_cyl, nr_sides):
        error.check(nr_sides == 2, "ADF: Must be double-sided")
        self.bitrate = 253
        self.sec_per_track = 11
        self.track_list = [None] * start_cyl


    @classmethod
    def to_file(cls, start_cyl, nr_sides):
        adf = cls(start_cyl, nr_sides)
        return adf


    @classmethod
    def from_file(cls, dat):

        adf = cls(0, 2)

        nsec = adf.sec_per_track
        error.check((len(dat) % (2*nsec*512)) == 0, "Bad ADF image")
        ncyl = len(dat) // (2*nsec*512)
        if ncyl > 90:
            ncyl //= 2
            nsec *= 2
            adf.bitrate *= 2
            adf.sec_per_track = nsec

        for i in range(ncyl*2):
            ados = amigados.AmigaDOS(tracknr=i, nsec=nsec)
            ados.set_adf_track(dat[i*nsec*512:(i+1)*nsec*512])
            adf.track_list.append(ados)

        return adf


    def get_track(self, cyl, side, writeout=False):
        off = cyl * 2 + side
        if off >= len(self.track_list):
            return None
        rawbytes = self.track_list[off].bits()
        tdat = bitarray(endian='big')
        tdat.frombytes(rawbytes)
        track = MasterTrack(
            bits = tdat,
            time_per_rev = 0.2)
        track.verify = self.track_list[off]
        return track


    def append_track(self, track):
        
        self.track_list.append(track)


    def get_image(self):

        tlen = self.sec_per_track * 512
        tdat = bytearray()

        for t in self.track_list:
            if t is None or not hasattr(t, 'get_adf_track'):
                tdat += bytes(tlen)
            else:
                tdat += t.get_adf_track()

        if len(self.track_list) < 160:
            tdat += bytes(tlen * (160 - len(self.track_list)))

        return tdat


# Local variables:
# python-indent: 4
# End:
