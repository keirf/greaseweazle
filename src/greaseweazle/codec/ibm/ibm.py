# greaseweazle/codec/ibm/ibm.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from typing import Any, List, Optional, Union

import re
from greaseweazle import error

def sec_sz(n):
    return 128 << n if n <= 7 else 128 << 8

class TrackArea:
    def __init__(self, start, end, crc=None):
        self.start = start
        self.end = end
        self.crc = crc
    def delta(self, delta):
        self.start -= delta
        self.end -= delta
    def __eq__(self, x):
        return (isinstance(x, type(self))
                and self.start == x.start
                and self.end == x.end
                and self.crc == x.crc)

class IDAM(TrackArea):
    def __init__(self, start, end, crc, c, h, r, n):
        super().__init__(start, end, crc)
        self.c = c
        self.h = h
        self.r = r
        self.n = n
    def __str__(self):
        return ("IDAM:%6d-%6d c=%02x h=%02x r=%02x n=%02x CRC:%04x"
                % (self.start, self.end, self.c, self.h, self.r, self.n,
                   self.crc))
    def __eq__(self, x):
        return (super().__eq__(x)
                and self.c == x.c and self.h == x.h
                and self.r == x.r and self.n == x.n)
    def __copy__(self):
        return IDAM(self.start, self.end, self.crc,
                    self.c, self.h, self.r, self.n)

class DAM(TrackArea):
    def __init__(self, start, end, crc, mark, data=None):
        super().__init__(start, end, crc)
        self.mark = mark
        self.data = data
    def __str__(self):
        return "DAM: %6d-%6d mark=%02x" % (self.start, self.end, self.mark)
    def __eq__(self, x):
        return (super().__eq__(x)
                and self.mark == x.mark
                and self.data == x.data)
    def __copy__(self):
        return DAM(self.start, self.end, self.crc, self.mark, self.data)

class Sector(TrackArea):
    def __init__(self, idam, dam):
        super().__init__(idam.start, dam.end, idam.crc | dam.crc)
        self.idam = idam
        self.dam = dam
    def __str__(self):
        s = "Sec: %6d-%6d CRC:%04x\n" % (self.start, self.end, self.crc)
        s += " " + str(self.idam) + "\n"
        s += " " + str(self.dam)
        return s
    def delta(self, delta):
        super().delta(delta)
        self.idam.delta(delta)
        self.dam.delta(delta)
    def __eq__(self, x):
        return (super().__eq__(x)
                and self.idam == x.idam
                and self.dam == x.dam)
    
class IAM(TrackArea):
    def __str__(self):
        return "IAM: %6d-%6d" % (self.start, self.end)
    def __copy__(self):
        return IAM(self.start, self.end)


class IBMTrack:

    IAM  = 0xfc
    IDAM = 0xfe
    DAM  = 0xfb
    DDAM = 0xf8

    # Subclasses must define these
    time_per_rev: float
    clock: float

    def __init__(self, cyl: int, head: int):
        self.cyl, self.head = cyl, head
        self.sectors: List[Sector] = []
        self.iams: List[IAM] = []

    def has_sec(self, sec_id):
        return self.sectors[sec_id].crc == 0

    def nr_missing(self):
        return len(list(filter(lambda x: x.crc != 0, self.sectors)))

    def flux(self, *args, **kwargs):
        return self.raw_track().flux(*args, **kwargs)

    # private helper for decode_raw()
    def add_deduped_areas(self, areas: List[TrackArea]) -> None:
        a: Optional[TrackArea]
        for a in areas:
            list: List[Any]
            if isinstance(a, IAM):
                list = self.iams
            elif isinstance(a, Sector):
                list = self.sectors
            else:
                continue
            for i, s in enumerate(list):
                if abs(s.start - a.start) < 1000:
                    if isinstance(a, Sector) and s.crc != 0 and a.crc == 0:
                        self.sectors[i] = a
                    a = None
                    break
            if a is not None:
                list.append(a)
        self.iams.sort(key=lambda x:x.start)
        self.sectors.sort(key=lambda x:x.start)

from greaseweazle.codec.ibm import fm, mfm

class IBMTrackFormat:

    default_revs = mfm.default_revs

    def __init__(self, format_name):
        self.secs = 0
        self.sz = []
        self.id = 1
        self.h = None
        self.format_name = format_name
        self.interleave = 1
        self.cskew, self.hskew = 0, 0
        self.rpm = 300
        self.gap1, self.gap2, self.gap3, self.gap4a = None, None, None, None
        self.iam = True
        self.rate = 0
        self.img_bps = None
        self.finalised = False

    def add_param(self, key, val):
        if key == 'secs':
            val = int(val)
            error.check(0 <= val <= 256, '%s out of range' % key)
            self.secs = val
        elif key == 'bps':
            self.sz = []
            for x in val.split(','):
                y = re.match(r'(\d+)\*(\d+)', x)
                if y is not None:
                    n, l = int(y.group(1)), int(y.group(2))
                else:
                    n, l = int(x), 1
                s = 0
                while True:
                    if n == 128<<s:
                        break
                    s += 1
                    error.check(s <= 6, 'bps value out of range')
                for _ in range(l):
                    self.sz.append(s)
        elif key == 'interleave':
            val = int(val)
            error.check(1 <= val <= 255, '%s out of range' % key)
            self.interleave = val
        elif key in ['id', 'cskew', 'hskew']:
            val = int(val)
            error.check(0 <= val <= 255, '%s out of range' % key)
            setattr(self, key, val)
        elif key in ['gap1', 'gap2', 'gap3', 'gap4a', 'h']:
            if val == 'auto':
                val = None
            else:
                val = int(val)
                error.check(0 <= val <= 255, '%s out of range' % key)
            setattr(self, key, val)
        elif key == 'iam':
            error.check(val in ['yes', 'no'], 'bad iam value')
            self.iam = val == 'yes'
        elif key in ['rate', 'rpm']:
            val = int(val)
            error.check(1 <= val <= 2000, '%s out of range' % key)
            setattr(self, key, val)
        elif key == 'img_bps':
            val = int(val)
            error.check(128 <= val <= 8192, '%s out of range' % key)
            self.img_bps = val
        else:
            raise error.Fatal('unrecognised track option %s' % key)

    def finalise(self):
        if self.finalised:
            return
        error.check(self.iam or self.gap1 is None,
                    'gap1 specified but no iam')
        error.check(self.secs == 0 or len(self.sz) != 0,
                    'sector size not specified')
        error.check((self.img_bps is None
                     or self.img_bps >= max(self.sz, default=0)),
                    'img_bps cannot be smaller than sector data size')
        self.finalised = True

    def mk_track(self, cyl, head):
        if self.format_name == 'ibm.mfm':
            t = mfm.IBM_MFM_Formatted.from_config(self, cyl, head)
        else:
            t = fm.IBM_FM_Formatted.from_config(self, cyl, head)
        return t

# Local variables:
# python-indent: 4
# End:
