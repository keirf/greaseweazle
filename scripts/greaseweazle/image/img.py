# greaseweazle/image/img.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from greaseweazle import error
from greaseweazle.codec.ibm import mfm
from .image import Image

class IMG(Image):

    default_format = 'ibm.mfm'

    def __init__(self):
        self.to_track = dict()


    @classmethod
    def from_file(cls, name):

        with open(name, "rb") as f:
            dat = f.read()

        img = cls()

        nsec = 18
        tsz = nsec * 512
        ncyl = len(dat) // (tsz*2)

        pos = 0
        for cyl in range(ncyl):
            for head in range(2):
                track = mfm.IBM_MFM_1M44(cyl, head)
                track.set_img_track(dat[pos:pos+tsz])
                pos += tsz
                img.to_track[cyl,head] = track

        return img


    def get_track(self, cyl, side):
        if (cyl,side) not in self.to_track:
            return None
        return self.to_track[cyl,side].raw_track()


    def emit_track(self, cyl, side, track):
        self.to_track[cyl,side] = track


    def get_image(self):

        tdat = bytearray()

        n_side = 2
        n_cyl = max(self.to_track.keys(), default=(0), key=lambda x:x[0])[0]
        n_cyl += 1

        for cyl in range(n_cyl):
            for head in range(n_side):
                if (cyl,head) in self.to_track:
                    tdat += self.to_track[cyl,head].get_img_track()

        return tdat


# Local variables:
# python-indent: 4
# End:
