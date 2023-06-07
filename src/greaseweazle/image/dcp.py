# greaseweazle/image/dim.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import struct

from greaseweazle import error
from greaseweazle.image.img import IMG
from greaseweazle.codec.formats import *
from .image import Image

from greaseweazle.codec import formats

class DCP(IMG):

    read_only = True

    @classmethod
    def from_file(cls, name, fmt):

        with open(name, "rb") as f:
            header = f.read(162)
            format_str = 'pc98.2hd'
            fmt = formats.formats[format_str]()
            dat = f.read()

        img = cls(name, fmt)

        pos = 0
        for t in fmt.max_tracks:
            cyl, head = t.cyl, t.head
            if img.sides_swapped:
                head ^= 1
            track = fmt.fmt(cyl, head)
            if cyl > 80:
                break
            if header[cyl * 2 + head] == 1:
                pos += track.set_img_track(dat[pos:])
                img.to_track[cyl,head] = track
            elif header[cyl * 2 + head] != 0:
                raise error.Fatal("DCP: Corrupt header.")
        img.format_str = format_str

        return img

# Local variables:
# python-indent: 4
# End:
