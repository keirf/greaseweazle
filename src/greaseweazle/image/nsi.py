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

from greaseweazle.image.img import IMG

class NSI(IMG):
    default_format = 'northstar.mfm.ds'

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
