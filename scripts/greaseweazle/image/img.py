# greaseweazle/image/img.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from greaseweazle import error
from greaseweazle.codec.ibm import mfm
from .image import Image

import greaseweazle.codec.formats

class IMG(Image):

    def __init__(self, name, fmt):
        self.to_track = dict()
        error.check(fmt is not None and fmt.img_compatible, """\
Sector image requires compatible format specifier
Compatible formats:\n%s"""
                    % greaseweazle.codec.formats.print_formats(
                        lambda k, v: v.img_compatible))
        self.filename = name
        self.fmt = fmt


    @classmethod
    def from_file(cls, name, fmt):

        with open(name, "rb") as f:
            dat = f.read()

        img = cls(name, fmt)

        pos = 0
        for t in fmt.tracks:
            cyl, head = t.cyl, t.head
            track = fmt.fmt(cyl, head)
            pos += track.set_img_track(dat[pos:])
            img.to_track[cyl,head] = track

        return img


    @classmethod
    def to_file(cls, name, fmt=None):
        return cls(name, fmt)


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
