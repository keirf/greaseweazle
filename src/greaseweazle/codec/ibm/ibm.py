# greaseweazle/codec/ibm/ibm.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from __future__ import annotations
from typing import Any, List, Optional, Union

import re
import copy, heapq, struct, functools
import itertools as it
from bitarray import bitarray
from enum import Enum
import crcmod.predefined

from greaseweazle import error
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

fm_sync_prefix = bitarray(endian='big')
fm_sync_prefix.frombytes(b'\xaa\xaa' + sync(0xf8))
fm_sync_prefix = fm_sync_prefix[:16+10]

fm_iam_sync_bytes = sync(0xfc, 0xd7)
fm_iam_sync = bitarray(endian='big')
fm_iam_sync.frombytes(b'\xaa\xaa' + fm_iam_sync_bytes)

mfm_iam_sync_bytes = b'\x52\x24' * 3
mfm_iam_sync = bitarray(endian='big')
mfm_iam_sync.frombytes(mfm_iam_sync_bytes)

mfm_sync_bytes = b'\x44\x89' * 3
mfm_sync = bitarray(endian='big')
mfm_sync.frombytes(mfm_sync_bytes)

def fm_encode(dat):
    out = bytearray()
    for x in dat:
        if (x & 0xaa) == 0:
            x |= 0xaa
        out.append(x)
    return bytes(out)

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

encode_list: List[int] = []
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

crc16 = crcmod.predefined.Crc('crc-ccitt-false')

def sec_sz(n):
    return 128 << n if n <= 7 else 128 << 8

class Mark:
    IAM  = 0xfc
    IDAM = 0xfe
    DAM  = 0xfb
    DDAM = 0xf8

class Mode(Enum):
    FM, MFM = range(2)

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

    # Subclasses must define these
    time_per_rev: float
    clock: float

    def __init__(self, cyl: int, head: int, mode: Mode):
        self.cyl, self.head = cyl, head
        self.sectors: List[Sector] = []
        self.iams: List[IAM] = []
        self.mode = mode
        if mode is Mode.FM:
            self.gap_presync = 6
            self.gapbyte = 0xff
        elif mode is Mode.MFM:
            self.gap_presync = 12
            self.gapbyte = 0x4e
        else:
            raise error.Fatal('Unrecognised IBM mode')

    def summary_string(self) -> str:
        nsec, nbad = len(self.sectors), self.nr_missing()
        s = "IBM %s (%d/%d sectors)" % (self.mode.name, nsec - nbad, nsec)
        return s

    def has_sec(self, sec_id):
        return self.sectors[sec_id].crc == 0

    def nr_missing(self):
        return len(list(filter(lambda x: x.crc != 0, self.sectors)))

    def flux(self, *args, **kwargs):
        return self.raw_track().flux(*args, **kwargs)

    def mfm_raw_track(self) -> bytes:

        areas = heapq.merge(self.iams, self.sectors, key=lambda x:x.start)
        t = bytes()

        for a in areas:
            start = a.start//16 - self.gap_presync
            gap = max(start - len(t)//2, 0)
            t += encode(bytes([self.gapbyte] * gap))
            t += encode(bytes(self.gap_presync))
            if isinstance(a, IAM):
                t += mfm_iam_sync_bytes
                t += encode(bytes([Mark.IAM]))
            elif isinstance(a, Sector):
                t += mfm_sync_bytes
                idam = bytes([0xa1, 0xa1, 0xa1, Mark.IDAM,
                              a.idam.c, a.idam.h, a.idam.r, a.idam.n])
                idam += struct.pack('>H', crc16.new(idam).crcValue)
                t += encode(idam[3:])
                start = a.dam.start//16 - self.gap_presync
                gap = max(start - len(t)//2, 0)
                t += encode(bytes([self.gapbyte] * gap))
                t += encode(bytes(self.gap_presync))
                t += mfm_sync_bytes
                dam = bytes([0xa1, 0xa1, 0xa1, a.dam.mark]) + a.dam.data
                dam += struct.pack('>H', crc16.new(dam).crcValue)
                t += encode(dam[3:])

        return t

    def fm_raw_track(self) -> bytes:

        areas = heapq.merge(self.iams, self.sectors, key=lambda x:x.start)
        t = bytes()

        for a in areas:
            start = a.start//16 - self.gap_presync
            gap = max(start - len(t)//2, 0)
            t += encode(bytes([self.gapbyte] * gap))
            t += encode(bytes(self.gap_presync))
            if isinstance(a, IAM):
                t += fm_iam_sync_bytes
            elif isinstance(a, Sector):
                idam = bytes([Mark.IDAM,
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

        return t

    def raw_track(self) -> MasterTrack:

        if self.mode is Mode.FM:
            t = self.fm_raw_track()
        else:
            t = self.mfm_raw_track()

        # Add the pre-index gap.
        tlen = int((self.time_per_rev / self.clock) // 16)
        gap = max(tlen - len(t)//2, 0)
        t += encode(bytes([self.gapbyte] * gap))

        if self.mode is Mode.FM:
            t = fm_encode(t)
        else:
            t = mfm_encode(t)

        track = MasterTrack(
            bits = t,
            time_per_rev = self.time_per_rev)
        track.verify = self
        track.verify_revs = default_revs
        return track

class IBMTrackRaw(IBMTrack):

    def mfm_decode_raw(self, track, pll=None) -> List[TrackArea]:
        flux = track.flux()
        flux.cue_at_index()
        raw = RawTrack(time_per_rev = self.time_per_rev,
                       clock = self.clock, data = flux, pll = pll)
        bits, _ = raw.get_all_data()

        areas: List[TrackArea] = []
        idam = None

        ## 1. Calculate offsets within dump
        
        for offs in bits.itersearch(mfm_iam_sync):
            if len(bits) < offs+4*16:
                continue
            mark = decode(bits[offs+3*16:offs+4*16].tobytes())[0]
            if mark == Mark.IAM:
                areas.append(IAM(offs, offs+4*16))
                self.has_iam = True

        for offs in bits.itersearch(mfm_sync):

            if len(bits) < offs+4*16:
                continue
            mark = decode(bits[offs+3*16:offs+4*16].tobytes())[0]
            if mark == Mark.IDAM:
                s, e = offs, offs+10*16
                if len(bits) < e:
                    continue
                b = decode(bits[s:e].tobytes())
                c,h,r,n = struct.unpack(">4x4B2x", b)
                crc = crc16.new(b).crcValue
                if idam is not None:
                    areas.append(idam)
                idam = IDAM(s, e, crc, c=c, h=h, r=r, n=n)
            elif mark == Mark.DAM or mark == Mark.DDAM:
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

        return areas

    def fm_decode_raw(self, track, pll=None) -> List[TrackArea]:
        flux = track.flux()
        flux.cue_at_index()
        raw = RawTrack(time_per_rev = self.time_per_rev,
                       clock = self.clock, data = flux, pll = pll)
        bits, _ = raw.get_all_data()

        areas: List[TrackArea] = []
        idam = None

        ## 1. Calculate offsets within dump
        
        for offs in bits.itersearch(fm_iam_sync):
            offs += 16
            areas.append(IAM(offs, offs+1*16))
            self.has_iam = True

        for offs in bits.itersearch(fm_sync_prefix):
            offs += 16
            if len(bits) < offs+1*16:
                continue
            mark = decode(bits[offs:offs+1*16].tobytes())[0]
            clock = decode(bits[offs-1:offs+1*16-1].tobytes())[0]
            if clock != 0xc7:
                continue
            if mark == Mark.IDAM:
                s, e = offs, offs+7*16
                if len(bits) < e:
                    continue
                b = decode(bits[s:e].tobytes())
                c,h,r,n = struct.unpack(">x4B2x", b)
                crc = crc16.new(b).crcValue
                if idam is not None:
                    areas.append(idam)
                idam = IDAM(s, e, crc, c=c, h=h, r=r, n=n)
            elif mark == Mark.DAM or mark == Mark.DDAM:
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
                    n += next(index)
                except StopIteration:
                    n = float('inf')
            a.delta(p)
        areas.sort(key=lambda x:x.start)

        return areas

    def decode_raw(self, track, pll=None) -> None:
        
        if self.mode is Mode.FM:
            areas = self.fm_decode_raw(track, pll)
        else:
            areas = self.mfm_decode_raw(track, pll)

        # Add to the deduped lists
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


class IBMTrackFormatted(IBMTrack):

    nsec: int

    def __init__(self, cyl: int, head: int, mode: Mode):
        super().__init__(cyl, head, mode)
        self.img_bps: Optional[int] = None
        self.raw = IBMTrackRaw(cyl, head, mode)

    def decode_raw(self, track, pll=None) -> None:
        self.raw.clock = self.clock
        self.raw.time_per_rev = self.time_per_rev
        self.raw.decode_raw(track, pll)
        mismatches = set()
        for r in self.raw.sectors:
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

    def set_img_track(self, tdat: bytearray) -> int:
        pos = 0
        self.sectors.sort(key = lambda x: x.idam.r)
        if self.img_bps is not None:
            totsize = len(self.sectors) * self.img_bps
        else:
            totsize = functools.reduce(lambda x, y: x + (128<<y.idam.n),
                                       self.sectors, 0)
        if len(tdat) < totsize:
            tdat += bytes(totsize - len(tdat))
        for s in self.sectors:
            s.crc = s.idam.crc = s.dam.crc = 0
            size = 128 << s.idam.n
            s.dam.data = tdat[pos:pos+size]
            if self.img_bps is not None:
                pos += self.img_bps
            else:
                pos += size
        self.sectors.sort(key = lambda x: x.start)
        return totsize

    def get_img_track(self) -> bytearray:
        tdat = bytearray()
        sectors = self.sectors.copy()
        sectors.sort(key = lambda x: x.idam.r)
        for s in sectors:
            tdat += s.dam.data
            if self.img_bps is not None:
                tdat += bytes(self.img_bps - len(s.dam.data))
        return tdat
        
    def verify_track(self, flux) -> bool:
        readback_track = self.__class__(self.cyl, self.head, self.mode)
        readback_track.clock = self.clock
        readback_track.time_per_rev = self.time_per_rev
        for iam in self.iams:
            readback_track.iams.append(copy.copy(iam))
        for sec in self.sectors:
            idam, dam = copy.copy(sec.idam), copy.copy(sec.dam)
            idam.crc, dam.crc = 0xffff, 0xffff
            readback_track.sectors.append(Sector(idam, dam))
        readback_track.decode_raw(flux)
        if readback_track.nr_missing() != 0:
            return False
        return self.sectors == readback_track.sectors


from greaseweazle.codec.ibm import fm, mfm

class IBMTrackFormat:

    default_revs = default_revs

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
