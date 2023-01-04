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

class DIM(IMG):
    default_format = None
    read_only = True

    @classmethod
    def from_file(cls, name, fmt):

        with open(name, "rb") as f:
            header = f.read(256)
            error.check(header[0xAB:0xB8] == b"DIFC HEADER  ",
                        "DIM: Not a DIM file.")
            (media_byte,) = struct.unpack('B255x', header)
            if media_byte == 0:
                format_str = 'pc98.2hd'
            elif media_byte == 1:
                format_str = 'pc98.2hs'
            else:
                raise error.Fatal("DIM: Unsupported format.")
            fmt = formats.get_format(format_str)
            dat = f.read()

        img = cls(name, fmt)

        pos = 0
        for t in fmt.tracks:
            cyl, head = t.cyl, t.head
            if img.sides_swapped:
                head ^= 1
            track = fmt.mk_track(cyl, head)
            if track is not None:
                pos += track.set_img_track(dat[pos:])
                img.to_track[cyl,head] = track
        img.format_str = format_str

        return img

# Local variables:
# python-indent: 4
# End:
