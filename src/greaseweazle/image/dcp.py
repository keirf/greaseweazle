# greaseweazle/image/dim.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import struct

from greaseweazle import error
from greaseweazle.image.img import IMG
from greaseweazle.codec import codec
from .image import Image

class DCP(IMG):

    read_only = True

    def from_bytes(self, dat: bytes) -> None:

        header = dat[:162]
        pos = 162
        format_str = 'pc98.2hd'
        fmt = codec.get_diskdef(format_str)
        assert fmt is not None # mypy

        for t in self.track_list():
            cyl, head = t.cyl, t.head
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
        self.format_str = format_str

# Local variables:
# python-indent: 4
# End:
