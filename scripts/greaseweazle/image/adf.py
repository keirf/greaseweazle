# greaseweazle/image/adf.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from greaseweazle import error
import greaseweazle.codec.amiga.amigados as amigados
from .image import Image

class ADF(Image):

    default_format = 'amiga.amigados'

    def __init__(self, start_cyl, nr_sides):
        error.check(nr_sides == 2, "ADF: Must be double-sided")
        self.sec_per_track = 11
        self.track_list = [None] * start_cyl


    @classmethod
    def from_file(cls, name):

        with open(name, "rb") as f:
            dat = f.read()

        adf = cls(0, 2)

        nsec = adf.sec_per_track
        error.check((len(dat) % (2*nsec*512)) == 0, "Bad ADF image")
        ncyl = len(dat) // (2*nsec*512)
        if ncyl > 90:
            ncyl //= 2
            nsec *= 2
            adf.sec_per_track = nsec

        for i in range(ncyl*2):
            ados = amigados.AmigaDOS(tracknr=i, nsec=nsec)
            ados.set_adf_track(dat[i*nsec*512:(i+1)*nsec*512])
            adf.track_list.append(ados)

        return adf


    def get_track(self, cyl, side):
        off = cyl * 2 + side
        if off >= len(self.track_list):
            return None
        return self.track_list[off].raw_track()


    def append_track(self, track):
        self.track_list.append(track)


    def get_image(self):

        tlen = self.sec_per_track * 512
        tdat = bytearray()

        for tracknr in range(len(self.track_list)):
            t = self.track_list[tracknr]
            if t is not None and hasattr(t, 'get_adf_track'):
                tdat += t.get_adf_track()
            elif tracknr < 160:
                # Pad empty/damaged tracks.
                tdat += bytes(tlen)
            else:
                # Do not extend past 160 tracks unless there is data.
                break

        if len(self.track_list) < 160:
            tdat += bytes(tlen * (160 - len(self.track_list)))

        return tdat


# Local variables:
# python-indent: 4
# End:
