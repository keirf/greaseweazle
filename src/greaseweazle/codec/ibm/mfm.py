# greaseweazle/codec/ibm/mfm.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import copy, heapq, struct, functools
import itertools as it
from bitarray import bitarray
import crcmod.predefined

from greaseweazle.track import MasterTrack, RawTrack

default_revs = 2

iam_sync_bytes = b'\x52\x24' * 3
iam_sync = bitarray(endian='big')
iam_sync.frombytes(iam_sync_bytes)

sync_bytes = b'\x44\x89' * 3
sync = bitarray(endian='big')
sync.frombytes(sync_bytes)

crc16 = crcmod.predefined.Crc('crc-ccitt-false')

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
    
class IBM_MFM:

    IAM  = 0xfc
    IDAM = 0xfe
    DAM  = 0xfb
    DDAM = 0xf8

    gap_presync = 12

    gapbyte = 0x4e

    def __init__(self, cyl, head):
        self.cyl, self.head = cyl, head
        self.sectors = []
        self.iams = []

    def summary_string(self):
        nsec, nbad = len(self.sectors), self.nr_missing()
        s = "IBM MFM (%d/%d sectors)" % (nsec - nbad, nsec)
        return s

    def has_sec(self, sec_id):
        return self.sectors[sec_id].crc == 0

    def nr_missing(self):
        return len(list(filter(lambda x: x.crc != 0, self.sectors)))

    def flux(self, *args, **kwargs):
        return self.raw_track().flux(*args, **kwargs)

    def decode_raw(self, track, pll=None):
        flux = track.flux()
        flux.cue_at_index()
        raw = RawTrack(time_per_rev = self.time_per_rev,
                       clock = self.clock, data = flux, pll = pll)
        bits, _ = raw.get_all_data()

        areas = []
        idam = None

        ## 1. Calculate offsets within dump
        
        for offs in bits.itersearch(iam_sync):
            if len(bits) < offs+4*16:
                continue
            mark = decode(bits[offs+3*16:offs+4*16].tobytes())[0]
            if mark == IBM_MFM.IAM:
                areas.append(IAM(offs, offs+4*16))
                self.has_iam = True

        for offs in bits.itersearch(sync):

            if len(bits) < offs+4*16:
                continue
            mark = decode(bits[offs+3*16:offs+4*16].tobytes())[0]
            if mark == IBM_MFM.IDAM:
                s, e = offs, offs+10*16
                if len(bits) < e:
                    continue
                b = decode(bits[s:e].tobytes())
                c,h,r,n = struct.unpack(">4x4B2x", b)
                crc = crc16.new(b).crcValue
                if idam is not None:
                    areas.append(idam)
                idam = IDAM(s, e, crc, c=c, h=h, r=r, n=n)
            elif mark == IBM_MFM.DAM or mark == IBM_MFM.DDAM:
                if idam is None or idam.end - offs > 1000:
                    areas.append(DAM(offs, offs+4*16, 0xffff, mark=mark))
                else:
                    sz = 128 << idam.n
                    s, e = offs, offs+(4+sz+2)*16
                    if len(bits) < e:
                        continue
                    b = decode(bits[s:e].tobytes())
                    crc = crc16.new(b).crcValue
                    dam = DAM(s, e, crc, mark=mark, data=b[4:-2])
                    areas.append(Sector(idam, dam))
                idam = None
            else:
                pass #print("Unknown mark %02x" % mark)

        if idam is not None:
            areas.append(idam)

        # Convert to offsets within track
        areas.sort(key=lambda x:x.start)
        index = iter(raw.revolutions)
        p, n = 0, next(index)
        for a in areas:
            if a.start >= n:
                p = n
                try:
                    n += next(index)
                except StopIteration:
                    n = float('inf')
            a.delta(p)
        areas.sort(key=lambda x:x.start)

        # Add to the deduped lists
        for a in areas:
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


    def raw_track(self):

        areas = heapq.merge(self.iams, self.sectors, key=lambda x:x.start)
        t = bytes()

        for a in areas:
            start = a.start//16 - self.gap_presync
            gap = max(start - len(t)//2, 0)
            t += encode(bytes([self.gapbyte] * gap))
            t += encode(bytes(self.gap_presync))
            if isinstance(a, IAM):
                t += iam_sync_bytes
                t += encode(bytes([self.IAM]))
            elif isinstance(a, Sector):
                t += sync_bytes
                idam = bytes([0xa1, 0xa1, 0xa1, self.IDAM,
                              a.idam.c, a.idam.h, a.idam.r, a.idam.n])
                idam += struct.pack('>H', crc16.new(idam).crcValue)
                t += encode(idam[3:])
                start = a.dam.start//16 - self.gap_presync
                gap = max(start - len(t)//2, 0)
                t += encode(bytes([self.gapbyte] * gap))
                t += encode(bytes(self.gap_presync))
                t += sync_bytes
                dam = bytes([0xa1, 0xa1, 0xa1, a.dam.mark]) + a.dam.data
                dam += struct.pack('>H', crc16.new(dam).crcValue)
                t += encode(dam[3:])

        # Add the pre-index gap.
        tlen = int((self.time_per_rev / self.clock) // 16)
        gap = max(tlen - len(t)//2, 0)
        t += encode(bytes([self.gapbyte] * gap))

        track = MasterTrack(
            bits = mfm_encode(t),
            time_per_rev = self.time_per_rev)
        track.verify = self
        track.verify_revs = default_revs
        return track


class IBM_MFM_Formatted(IBM_MFM):

    gap_4a = 80 # Post-Index
    gap_1  = 50 # Post-IAM
    gap_2  = 22 # Post-IDAM

    def __init__(self, cyl, head):

        super().__init__(cyl, head)
        self.raw_iams, self.raw_sectors = [], []

    def decode_raw(self, track, pll=None):
        iams, sectors = self.iams, self.sectors
        self.iams, self.sectors = self.raw_iams, self.raw_sectors
        super().decode_raw(track, pll)
        self.iams, self.sectors = iams, sectors
        mismatches = set()
        for r in self.raw_sectors:
            if r.idam.crc != 0:
                continue
            matched = False
            for s in self.sectors:
                if (s.idam.c == r.idam.c and
                    s.idam.h == r.idam.h and
                    s.idam.r == r.idam.r and
                    s.idam.n == r.idam.n):
                    s.idam.crc = 0
                    matched = True
                    if r.dam.crc == 0 and s.dam.crc != 0:
                        s.dam.crc = s.crc = 0
                        s.dam.data = r.dam.data
            if not matched:
                mismatches.add((r.idam.c, r.idam.h, r.idam.r, r.idam.n))
        for m in mismatches:
            print('T%d.%d: Ignoring unexpected sector C:%d H:%d R:%d N:%d'
                  % (self.cyl, self.head, *m))

    def set_img_track(self, tdat):
        pos = 0
        self.sectors.sort(key = lambda x: x.idam.r)
        totsize = functools.reduce(lambda x, y: x + (128<<y.idam.n),
                                   self.sectors, 0)
        if len(tdat) < totsize:
            tdat += bytes(totsize - len(tdat))
        for s in self.sectors:
            s.crc = s.idam.crc = s.dam.crc = 0
            size = 128 << s.idam.n
            s.dam.data = tdat[pos:pos+size]
            pos += size
        self.sectors.sort(key = lambda x: x.start)
        return totsize

    def get_img_track(self):
        tdat = bytearray()
        sectors = self.sectors.copy()
        sectors.sort(key = lambda x: x.idam.r)
        for s in sectors:
            tdat += s.dam.data
        return tdat
        
    def verify_track(self, flux):
        readback_track = IBM_MFM_Formatted(self.cyl, self.head)
        readback_track.clock = self.clock
        readback_track.time_per_rev = self.time_per_rev
        for x in self.iams:
            readback_track.iams.append(copy.copy(x))
        for x in self.sectors:
            idam, dam = copy.copy(x.idam), copy.copy(x.dam)
            idam.crc, dam.crc = 0xffff, 0xffff
            readback_track.sectors.append(Sector(idam, dam))
        readback_track.decode_raw(flux)
        if readback_track.nr_missing() != 0:
            return False
        return self.sectors == readback_track.sectors


class IBM_MFM_Predefined(IBM_MFM_Formatted):

    cskew = 0
    hskew = 0
    interleave = 1
    hswap = False

    def __init__(self, cyl, head):

        super().__init__(cyl, head)

        if self.hswap:
            head = 1-head

        # Create logical sector map in rotational order
        sec_map = [-1] * self.nsec
        pos = (cyl*self.cskew + head*self.hskew) % self.nsec
        for i in range(self.nsec):
            while sec_map[pos] != -1:
                pos = (pos + 1) % self.nsec
            sec_map[pos] = i
            pos = (pos + self.interleave) % self.nsec

        pos = self.gap_4a
        if self.gap_1 is not None:
            self.iams = [IAM(pos*16,(pos+4)*16)]
            pos += 4 + self.gap_1

        for i in range(self.nsec):
            pos += self.gap_presync
            idam = IDAM(pos*16, (pos+10)*16, 0xffff,
                        c=cyl, h=head, r=self.id0+sec_map[i], n = self.sz)
            pos += 10 + self.gap_2 + self.gap_presync
            size = 128 << self.sz
            dam = DAM(pos*16, (pos+4+size+2)*16, 0xffff,
                      mark=self.DAM, data=bytes(size))
            self.sectors.append(Sector(idam, dam))
            pos += 4 + size + 2 + self.gap_3

    @classmethod
    def decode_track(cls, cyl, head, track):
        mfm = cls(cyl, head)
        mfm.decode_raw(track)
        return mfm


class IBM_MFM_720(IBM_MFM_Predefined):

    time_per_rev = 0.2
    clock = 2e-6
    
    gap_3  = 84 # Post-DAM
    nsec   = 9
    id0    = 1
    sz     = 2

class IBM_MFM_800(IBM_MFM_720):

    gap_3  = 30
    nsec   = 10

class IBM_MFM_1200(IBM_MFM_720):

    time_per_rev = 60/360
    clock = 1e-6
    nsec   = 15

class IBM_MFM_1440(IBM_MFM_720):

    clock = 1e-6
    nsec  = 18

class IBM_MFM_1680(IBM_MFM_720):

    clock = 1e-6
    nsec  = 21
    gap_3 = 12
    cskew = 3
    interleave = 2

class IBM_MFM_2880(IBM_MFM_720):

    clock = 5e-7
    gap_2 = 41
    nsec  = 36

class AtariST_SS_9SPT(IBM_MFM_720):

    gap_1 = None
    cskew = 2

class AtariST_DS_9SPT(IBM_MFM_720):

    gap_1 = None
    cskew = 4
    hskew = 2

class AtariST_10SPT(IBM_MFM_720):

    gap_1 = None
    gap_3 = 30
    nsec  = 10

class AtariST_11SPT(IBM_MFM_720):

    clock = 2e-6 * 0.96 # long track
    gap_1 = None
    gap_3 = 3
    nsec  = 11

class Acorn_ADFS_640(IBM_MFM_Predefined):

    time_per_rev = 0.2
    clock = 2e-6

    gap_3 = 57
    nsec  = 16
    id0   = 0
    sz    = 1

class Acorn_ADFS_800(IBM_MFM_Predefined):

    time_per_rev = 0.2
    clock = 2e-6

    gap_3 = 116
    nsec  = 5
    id0   = 0
    sz    = 3

class Acorn_ADFS_1600(IBM_MFM_Predefined):

    time_per_rev = 0.2
    clock = 1e-6

    gap_3 = 116
    nsec  = 10
    id0   = 0
    sz    = 3

class Commodore_1581(IBM_MFM_720):

    gap_3 = 30
    nsec  = 10
    hswap = True

class Akai_800(IBM_MFM_720):

    gap_3 = 116
    nsec  = 5
    id0   = 1
    sz    = 3
    cskew = 2

class Akai_1600(Akai_800):

    clock = 1e-6
    nsec  = 10
    cskew = 5

class Ensoniq_800(IBM_MFM_720):

    gap_3 = 30
    nsec  = 10
    id0   = 0

class Ensoniq_1600(IBM_MFM_720):

    clock = 1e-6
    gap_3 = 40
    nsec  = 20
    id0   = 0

class PC98_DD(IBM_MFM_1200):

    clock = 2e-6
    gap_3 = 57
    nsec  = 8
    sz    = 2

class PC98_HD(IBM_MFM_1200):

    gap_3 = 116
    nsec  = 8
    sz    = 3

class PC98_2HS(IBM_MFM_1440):

    gap_3 = 116
    nsec  = 9
    sz    = 3

class Sega_SF7000(IBM_MFM_Predefined):

    time_per_rev = 0.2
    clock = 2e-6

    gap_3 = 42
    nsec  = 16
    id0   = 1
    sz    = 1


def mfm_encode(dat):
    y = 0
    out = bytearray()
    for x in dat:
        y = (y<<8) | x
        if (x & 0xaa) == 0:
            y |= ~((y>>1)|(y<<1)) & 0xaaaa
        y &= 255
        out.append(y)
    return bytes(out)

encode_list = []
for x in range(256):
    y = 0
    for i in range(8):
        y <<= 2
        y |= (x >> (7-i)) & 1
    encode_list.append(y)

def encode(dat):
    out = bytearray()
    for x in dat:
        out += struct.pack('>H', encode_list[x])
    return bytes(out)
    
decode_list = bytearray()
for x in range(0x5555+1):
    y = 0
    for i in range(16):
        if x&(1<<(i*2)):
            y |= 1<<i
    decode_list.append(y)

def decode(dat):
    out = bytearray()
    for x,y in zip(dat[::2], dat[1::2]):
        out.append(decode_list[((x<<8)|y)&0x5555])
    return bytes(out)


# Local variables:
# python-indent: 4
# End:
