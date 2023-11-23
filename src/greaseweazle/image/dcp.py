# greaseweazle/image/dcp.py
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

class DCP(IMG_AutoFormat):

    read_only = True

    @staticmethod
    def format_from_file(name: str) -> str:
        return 'pc98.2hd'

    def from_bytes(self, dat: bytes) -> None:

        header = dat[:162]
        pos = 162
        fmt = self.fmt

        for cyl, head in self.track_list():
            if self.sides_swapped:
                head ^= 1
            track = fmt.mk_track(cyl, head)
            if track is None:
                continue
            if cyl > 80:
                break
            if header[cyl * 2 + head] == 1:
                pos += track.set_img_track(dat[pos:])
                self.to_track[cyl,head] = track
            elif header[cyl * 2 + head] != 0:
                raise error.Fatal("DCP: Corrupt header.")

# Local variables:
# python-indent: 4
# End:
