# greaseweazle/codec/ibm/fm.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import binascii
import copy, heapq, struct, functools
import itertools as it
from bitarray import bitarray
import crcmod.predefined

from greaseweazle.codec.ibm import mfm
from greaseweazle.track import MasterTrack, RawTrack

default_revs = 2

def sync(dat, clk=0xc7):
    x = 0
    for i in range(8):
        x <<= 1
        x |= (clk >> (7-i)) & 1
        x <<= 1
        x |= (dat >> (7-i)) & 1
    return bytes(struct.pack('>H', x))

sync_prefix = bitarray(endian='big')
sync_prefix.frombytes(b'\xaa\xaa' + sync(0xf8))
sync_prefix = sync_prefix[:16+10]

iam_sync_bytes = sync(0xfc, 0xd7)
iam_sync = bitarray(endian='big')
iam_sync.frombytes(b'\xaa\xaa' + iam_sync_bytes)

crc16 = crcmod.predefined.Crc('crc-ccitt-false')

sec_sz = mfm.sec_sz
IDAM   = mfm.IDAM
DAM    = mfm.DAM
Sector = mfm.Sector
IAM    = mfm.IAM
    
class IBM_FM:

    IAM  = 0xfc
    IDAM = 0xfe
    DAM  = 0xfb
    DDAM = 0xf8

    gap_presync = 6

    gapbyte = 0xff

    def __init__(self, cyl, head):
        self.cyl, self.head = cyl, head
        self.sectors = []
        self.iams = []

    def summary_string(self):
        nsec, nbad = len(self.sectors), self.nr_missing()
        s = "IBM FM (%d/%d sectors)" % (nsec - nbad, nsec)
        return s

    def has_sec(self, sec_id):
        return self.sectors[sec_id].crc == 0

    def nr_missing(self):
        return len(list(filter(lambda x: x.crc != 0, self.sectors)))

    def flux(self, *args, **kwargs):
        return self.raw_track().flux(*args, **kwargs)


    def decode_raw(self, track):
        flux = track.flux()
        flux.cue_at_index()
        raw = RawTrack(time_per_rev = self.time_per_rev,
                       clock = self.clock, data = flux)
        bits, _ = raw.get_all_data()

        areas = []
        idam = None

        ## 1. Calculate offsets within dump
        
        for offs in bits.itersearch(iam_sync):
            offs += 16
            areas.append(IAM(offs, offs+1*16))
            self.has_iam = True

        for offs in bits.itersearch(sync_prefix):
            offs += 16
            if len(bits) < offs+1*16:
                continue
            mark = decode(bits[offs:offs+1*16].tobytes())[0]
            clock = decode(bits[offs-1:offs+1*16-1].tobytes())[0]
            if clock != 0xc7:
                continue
            if mark == IBM_FM.IDAM:
                s, e = offs, offs+7*16
                if len(bits) < e:
                    continue
                b = decode(bits[s:e].tobytes())
                c,h,r,n = struct.unpack(">x4B2x", b)
                crc = crc16.new(b).crcValue
                if idam is not None:
                    areas.append(idam)
                idam = IDAM(s, e, crc, c=c, h=h, r=r, n=n)
            elif mark == IBM_FM.DAM or mark == IBM_FM.DDAM:
                if idam is None or idam.end - offs > 1000:
                    areas.append(DAM(offs, offs+4*16, 0xffff, mark=mark))
                else:
                    sz = 128 << idam.n
                    s, e = offs, offs+(1+sz+2)*16
                    if len(bits) < e:
                        continue
                    b = decode(bits[s:e].tobytes())
                    crc = crc16.new(b).crcValue
                    dam = DAM(s, e, crc, mark=mark, data=b[1:-2])
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
                    n = next(index)
                except StopIteration:
                    n = float('inf')
            a.delta(p)
        areas.sort(key=lambda x:x.start)

        # Add to the deduped lists
        for a in areas:
            match = False
            if isinstance(a, IAM):
                list = self.iams
            elif isinstance(a, Sector):
                list = self.sectors
            else:
                continue
            for s in list:
                if abs(s.start - a.start) < 1000:
                    match = True
                    break
            if match and isinstance(a, Sector) and s.crc != 0 and a.crc == 0:
                self.sectors = [x for x in self.sectors if x != a]
                match = False
            if not match:
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
            elif isinstance(a, Sector):
                idam = bytes([self.IDAM,
                              a.idam.c, a.idam.h, a.idam.r, a.idam.n])
                idam += struct.pack('>H', crc16.new(idam).crcValue)
                t += sync(idam[0]) + encode(idam[1:])
                start = a.dam.start//16 - self.gap_presync
                gap = max(start - len(t)//2, 0)
                t += encode(bytes([self.gapbyte] * gap))
                t += encode(bytes(self.gap_presync))
                dam = bytes([a.dam.mark]) + a.dam.data
                dam += struct.pack('>H', crc16.new(dam).crcValue)
                t += sync(dam[0]) + encode(dam[1:])

        # Add the pre-index gap.
        tlen = int((self.time_per_rev / self.clock) // 16)
        gap = max(tlen - len(t)//2, 0)
        t += encode(bytes([self.gapbyte] * gap))

        track = MasterTrack(
            bits = t,
            time_per_rev = self.time_per_rev)
        track.verify = self
        track.verify_revs = default_revs
        return track


class IBM_FM_Formatted(IBM_FM):

    gap_4a = 40 # Post-Index
    gap_1  = 26 # Post-IAM
    gap_2  = 11 # Post-IDAM

    def __init__(self, cyl, head):

        super().__init__(cyl, head)
        self.raw_iams, self.raw_sectors = [], []

    def decode_raw(self, track):
        iams, sectors = self.iams, self.sectors
        self.iams, self.sectors = self.raw_iams, self.raw_sectors
        super().decode_raw(track)
        self.iams, self.sectors = iams, sectors
        for r in self.raw_sectors:
            if r.idam.crc != 0:
                continue
            for s in self.sectors:
                if (s.idam.c == r.idam.c and
                    s.idam.h == r.idam.h and
                    s.idam.r == r.idam.r and
                    s.idam.n == r.idam.n):
                    s.idam.crc = 0
                    if r.dam.crc == 0 and s.dam.crc != 0:
                        s.dam.crc = s.crc = 0
                        s.dam.data = r.dam.data

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
        readback_track = IBM_FM_Formatted(self.cyl, self.head)
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


class IBM_FM_Predefined(IBM_FM_Formatted):

    cskew = 0
    hskew = 0
    interleave = 1
    
    def __init__(self, cyl, head):

        super().__init__(cyl, head)

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
            self.iams = [IAM(pos*16,(pos+1)*16)]
            pos += 1 + self.gap_1

        for i in range(self.nsec):
            pos += self.gap_presync
            idam = IDAM(pos*16, (pos+7)*16, 0xffff,
                        c=cyl, h=head, r=self.id0+sec_map[i], n = self.sz)
            pos += 7 + self.gap_2 + self.gap_presync
            size = 128 << self.sz
            dam = DAM(pos*16, (pos+1+size+2)*16, 0xffff,
                      mark=self.DAM, data=bytes(size))
            self.sectors.append(Sector(idam, dam))
            pos += 1 + size + 2 + self.gap_3

    @classmethod
    def decode_track(cls, cyl, head, track):
        mfm = cls(cyl, head)
        mfm.decode_raw(track)
        return mfm


class Acorn_DFS(IBM_FM_Predefined):

    time_per_rev = 0.2
    clock = 4e-6

    gap_1  = 0 # No IAM
    gap_3  = 21
    nsec   = 10
    id0    = 0
    sz     = 1
    cskew  = 3


encode_list = []
for x in range(256):
    y = 0
    for i in range(8):
        y <<= 1
        y |= 1
        y <<= 1
        y |= (x >> (7-i)) & 1
    encode_list.append(y)

def encode(dat):
    out = bytearray()
    for x in dat:
        out += struct.pack('>H', encode_list[x])
    return bytes(out)

decode = mfm.decode


# Local variables:
# python-indent: 4
# End:
