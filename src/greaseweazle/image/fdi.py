# greaseweazle/image/fdi.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import struct

from greaseweazle import error
from greaseweazle.image.img import IMG
from .image import Image

from greaseweazle.codec import formats

class FDI(IMG):
    default_format = 'pc98.2hd'
    read_only = True

    @classmethod
    def from_file(cls, name, fmt):

        with open(name, "rb") as f:
            header = f.read(32)
            (magic, fdd_type, headerSize, sectorSize, sectorsPerTrack, sides, tracks) = \
                struct.unpack('<LLL4xLLLL', header)
            error.check(magic == 0, "FDI: Not a FDI file.")
            error.check(fdd_type == 0x90, "FDI: Unsupported format.")
            error.check(sectorSize == 1024, "FDI: Unsupported sector size.")
            error.check(sectorsPerTrack == 8, "FDI: Unsupported number of sectors per track.")
            error.check(sides == 2, "FDI: Unsupported number of sides.")
            error.check(tracks == 77, "FDI: Unsupported number of tracks.")
            f.seek(headerSize)
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

        return img

# Local variables:
# python-indent: 4
# End:
