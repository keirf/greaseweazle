# greaseweazle/image/fd.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.
#
# .fd is a widely used format in the Thomson MO/TO community.
# .fd is directly supported by emulators such as DCMOTO.
# The main difference between IMG and FD is that FD completely separates both sides of a disk,
# i-e, all tacks/sectors of side 0 are stored before all tracks/sectors of side 1.

from greaseweazle.image.img import IMG

class FD(IMG):
    default_format = 'thomson.1s320'    # Most commonly used format
    sequential = True                   # while side 0 before whole side 1

# Local variables:
# python-indent: 4
# End:
