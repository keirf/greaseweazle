# greaseweazle/image/dim.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import struct

from greaseweazle import error
from greaseweazle.image.img import IMG_AutoFormat
from greaseweazle.codec import codec
from .image import Image

class DIM(IMG_AutoFormat):

    read_only = True

    @staticmethod
    def format_from_file(name: str) -> str:

        with open(name, "rb") as f:
            header = f.read(256)

        error.check(header[0xAB:0xB8] == b"DIFC HEADER  ",
                    "DIM: Not a DIM file.")
        media_byte, = struct.unpack('B255x', header)
        if media_byte == 0:
            format_str = 'pc98.2hd'
        elif media_byte == 1:
            format_str = 'pc98.2hs'
        else:
            raise error.Fatal("DIM: Unsupported format.")

        return format_str

    def from_bytes(self, dat: bytes) -> None:

        pos = 256
        fmt = self.fmt

        for t in fmt.tracks:
            cyl, head = t.cyl, t.head
            if self.sides_swapped:
                head ^= 1
            track = fmt.mk_track(cyl, head)
            if track is not None:
                pos += track.set_img_track(dat[pos:])
                self.to_track[cyl,head] = track

# Local variables:
# python-indent: 4
# End:
