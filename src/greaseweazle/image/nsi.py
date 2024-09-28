# greaseweazle/image/nsi.py
#
# North Star Image order:
#  1. All tracks of side 0
#  2. All tracks of side 1 (reverse order)
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import os

from greaseweazle import error
from greaseweazle.image.img import IMG_AutoFormat

class NSI(IMG_AutoFormat):

    @staticmethod
    def format_from_file(name: str) -> str:
        size = os.path.getsize(name)
        if size == 1*35*10*256:
            return 'northstar.fm.ss'
#        if size == 2*35*10*256:
#            return 'northstar.fm.ds'
        if size == 1*35*10*512:
            return 'northstar.mfm.ss'
        if size == 2*35*10*512:
            return 'northstar.mfm.ds'
        raise error.Fatal(f'NSI: {name}: unrecognised file size')

    def track_list(self):
        t, l = self.fmt.tracks, []
        prepend = False
        for h in t.heads:
            _l = []
            for c in t.cyls:
                _l.append((c,h))
            if (h & 1) == 1:
                _l.reverse()
            l += _l
        return l


# Local variables:
# python-indent: 4
# End:
