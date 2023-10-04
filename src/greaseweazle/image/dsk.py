# greaseweazle/image/dsk.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from greaseweazle.image.image import Image
from greaseweazle.image.img import IMG
from greaseweazle.image.edsk import EDSK

class DSK(IMG):

    @classmethod
    def from_file(cls, name: str, fmt) -> Image:

        with open(name, "rb") as f:
            sig = f.read(16)

        if sig[:8] == b'MV - CPC' or sig[:16] == b'EXTENDED CPC DSK':
            return EDSK.from_file(name, fmt)

        return IMG.from_file(name, fmt)

# Local variables:
# python-indent: 4
# End:
