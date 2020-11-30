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

    def __init__(self):
        self.sec_per_track = 11
        self.to_track = dict()


    @classmethod
    def from_file(cls, name):

        with open(name, "rb") as f:
            dat = f.read()

        adf = cls()

        nsec = adf.sec_per_track
        error.check((len(dat) % (2*nsec*512)) == 0, "Bad ADF image")
        ncyl = len(dat) // (2*nsec*512)
        if ncyl > 90:
            ncyl //= 2
            nsec *= 2
            adf.sec_per_track = nsec

        for tnr in range(ncyl*2):
            ados = amigados.AmigaDOS(tracknr=tnr, nsec=nsec)
            ados.set_adf_track(dat[tnr*nsec*512:(tnr+1)*nsec*512])
            adf.to_track[tnr] = ados

        return adf


    def get_track(self, cyl, side):
        tnr = cyl * 2 + side
        if not tnr in self.to_track:
            return None
        return self.to_track[tnr].raw_track()


    def emit_track(self, cyl, side, track):
        tnr = cyl * 2 + side
        self.to_track[tnr] = track


    def get_image(self):

        tlen = self.sec_per_track * 512
        tdat = bytearray()

        ntracks = max(self.to_track, default=0) + 1

        for tnr in range(ntracks):
            t = self.to_track[tnr] if tnr in self.to_track else None
            if t is not None and hasattr(t, 'get_adf_track'):
                tdat += t.get_adf_track()
            elif tnr < 160:
                # Pad empty/damaged tracks.
                tdat += bytes(tlen)
            else:
                # Do not extend past 160 tracks unless there is data.
                break

        if ntracks < 160:
            tdat += bytes(tlen * (160 - ntracks))

        return tdat


# Local variables:
# python-indent: 4
# End:
