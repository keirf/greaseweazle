# greaseweazle/image/d64.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import struct

from greaseweazle import error
from greaseweazle.image.image import Image
from greaseweazle.image.img import IMG
from greaseweazle.codec.commodore import c64_gcr

class D64(IMG):
    default_format = 'commodore.1541'
    min_cyls = 35

    def get_disk_id(self):
        t = self.get_track(17, 0) # BAM, track 18 (counting from 1), sector 0
        if t is None:
            return None
        dat = t.get_img_track()
        if len(dat) < 164:
            return None
        # NB disk_id byte order in BAM is reverse of sector headers
        disk_id, = struct.unpack('<H', dat[162:164])
        return disk_id

    @classmethod
    def from_file(cls, name: str, fmt) -> Image:
        img = super(cls, cls).from_file(name, fmt)
        assert isinstance(img, D64)
        disk_id = img.get_disk_id()
        for _, t in img.to_track.items():
            error.check(issubclass(type(t), c64_gcr.C64GCR),
                        'D64: Only commodore.1541 format is supported')
            if disk_id is not None:
                t.set_disk_id(disk_id)
        return img

# Local variables:
# python-indent: 4
# End:
