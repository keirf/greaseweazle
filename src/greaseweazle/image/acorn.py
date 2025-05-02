# greaseweazle/image/acorn.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from greaseweazle.image.img import IMG

class SSD(IMG):
    default_format = 'acorn.dfs.ss'
    sequential = True

class DSD(IMG):
    default_format = 'acorn.dfs.ds'

class ADS(IMG):
    default_format = 'acorn.adfs.160'
    
class ADM(IMG):
    default_format = 'acorn.adfs.320'
    
class ADL(IMG):
    default_format = 'acorn.adfs.640'

# Local variables:
# python-indent: 4
# End:
