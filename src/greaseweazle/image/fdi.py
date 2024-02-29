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

class FDI(IMG):
    default_format = 'pc98.2hd'
    read_only = True

    def from_bytes(self, dat: bytes) -> None:

        (magic, fdd_type, header_size, sector_size, sectors_per_track,
         sides, tracks) = struct.unpack('<LLL4xLLLL', dat[:32])
        error.check(magic == 0, 'FDI: Not a FDI file.')
        error.check(fdd_type == 0x90, 'FDI: Unsupported format.')
        error.check(sector_size == 1024, 'FDI: Unsupported sector size.')
        error.check(sectors_per_track == 8,
                    'FDI: Unsupported number of sectors per track.')
        error.check(sides == 2, 'FDI: Unsupported number of sides.')
        error.check(tracks == 77, 'FDI: Unsupported number of tracks.')

        pos = header_size
        for cyl, head in self.track_list():
            if self.sides_swapped:
                head ^= 1
            track = self.fmt.mk_track(cyl, head)
            if track is not None:
                pos += track.set_img_track(dat[pos:])
                self.to_track[cyl,head] = track

# Local variables:
# python-indent: 4
# End:
