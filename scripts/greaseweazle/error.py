# greaseweazle/error.py
#
# Error management and reporting.
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

class Fatal(Exception):
    pass

def check(pred, desc):
    if not pred:
        raise Fatal(desc)
    
# Local variables:
# python-indent: 4
# End:
