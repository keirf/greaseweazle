# greaseweazle/image/d81.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from greaseweazle.image.img import IMG

class D81(IMG):
    default_format = 'commodore.1581'
    sides_swapped = True

class D1M(IMG):
    default_format = 'commodore.cmd.fd2000.dd'
    sides_swapped = True

class D2M(IMG):
    default_format = 'commodore.cmd.fd2000.hd'
    sides_swapped = True

class D4M(IMG):
    default_format = 'commodore.cmd.fd4000.ed'
    sides_swapped = True

# Local variables:
# python-indent: 4
# End:
