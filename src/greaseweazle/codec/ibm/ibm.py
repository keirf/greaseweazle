# greaseweazle/codec/ibm/ibm.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from __future__ import annotations
from typing import Any, List, Optional, Union, Tuple

import re
import copy, heapq, struct, functools
import itertools as it
from bitarray import bitarray
from enum import Enum
import crcmod.predefined

from greaseweazle import error
from greaseweazle.codec import codec
from greaseweazle.track import MasterTrack, PLL, PLLTrack
from greaseweazle.flux import Flux, HasFlux

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
doubler = encode

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

# Create logical sector map in rotational order
def sec_map(nsec: int, interleave: int, cskew: int, hskew: int,
            cyl: int, head: int) -> List[int]:
    sec_map, pos = [-1] * nsec, 0
    if nsec != 0:
        pos = (cyl*cskew + head*hskew) % nsec
    for i in range(nsec):
        while sec_map[pos] != -1:
            pos = (pos + 1) % nsec
        sec_map[pos] = i
        pos = (pos + interleave) % nsec
    return sec_map

def sec_sz(n):
    return 128 << n if n <= 7 else 128 << 8

class Gaps:
    def __init__(self, gap1, gap2, gap3, gap4a):
        self.gap1 = gap1 # Post IAM
        self.gap2 = gap2 # Post IDAM
        self.gap3 = gap3 # Post DAM
        self.gap4a = gap4a # Post Index

FMGaps = Gaps(
    gap1 = 26,
    gap2 = 11,
    gap3 = [ 27, 42, 58, 138, 255, 255, 255, 255 ],
    gap4a = 40
)

MFMGaps = Gaps(
    gap1 = 50,
    gap2 = 22,
    gap3 = [ 32, 54, 84, 116, 255, 255, 255, 255 ],
    gap4a = 80
)


class Mark:
    IAM  = 0xfc
    IDAM = 0xfe
    DAM  = 0xfb
    DDAM = 0xf8
    # DEC RX02
    DAM_DEC_MMFM = 0xfd
    DDAM_DEC_MMFM = 0xf9
    # TRS-80
    DAM_TRS80_DIR = 0xfa

class Mode(Enum):
    FM, MFM, DEC_RX02 = range(3)
    def __str__(self):
        NAMES = [ 'IBM FM', 'IBM MFM', 'DEC RX02' ]
        return f'{NAMES[self.value]}'

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
                and abs(self.start - x.start) < 1000
                and abs(self.end - x.end) < 1000
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


class DEC_MMFM:
    def __init__(self):
        # Encode: 011110 -> 01000100010
        self.encode_search = bitarray('011110', endian='big')
        self.encode_replace = bitarray('01000100010', endian='big')
        # Decode: DCD=000 -> 11
        self.decode_search = bitarray('000', endian='big')
        self.decode_replace = bitarray('101', endian='big')
        sync_prefix = bitarray(endian='big')
        sync_prefix.frombytes(doubler(b'\xaa\xaa' + sync(0xf8)))
        self.sync_prefix = sync_prefix[:len(fm_sync_prefix)*2]
    def encode(self, pre: bytes) -> bytes:
        pre_bits = bitarray(endian='big')
        pre_bits.frombytes(pre)
        post_bits = bitarray(endian='big')
        post_bits.frombytes(mfm_encode(encode(pre)))
        for x in pre_bits.search(self.encode_search):
            post_bits[x*2+1:x*2+12] = self.encode_replace
        return post_bits.tobytes()
    def decode(self, bits: bitarray) -> bytes:
        for x in bits.search(self.decode_search):
            if x&1 != 0: # Only matches starting on a data bit
                bits[x:x+3] = self.decode_replace
        return decode(bits.tobytes())

dec_mmfm = DEC_MMFM()

class IBMTrack(codec.Codec):

    # Subclasses must define these
    time_per_rev: float
    clock: float

    verify_revs: float = 1

    def __init__(self, cyl: int, head: int, mode: Mode):
        self.cyl, self.head = cyl, head
        self.sectors: List[Sector] = []
        self.iams: List[IAM] = []
        self.mode = mode
        if mode is Mode.FM or mode is Mode.DEC_RX02:
            self.gap_presync = 6
            self.gapbyte = 0xff
        elif mode is Mode.MFM:
            self.gap_presync = 12
            self.gapbyte = 0x4e
        else:
            raise error.Fatal('Unrecognised IBM mode')
        self.img_bps: Optional[int] = None

    @property
    def nsec(self) -> int:
        return len(self.sectors)

    def summary_string(self) -> str:
        nsec, nbad = len(self.sectors), self.nr_missing()
        s = "%s (%d/%d sectors)" % (str(self.mode), nsec - nbad, nsec)
        return s

    def has_sec(self, sec_id: int):
        return self.sectors[sec_id].crc == 0

    def nr_missing(self) -> int:
        return len(list(filter(lambda x: x.crc != 0, self.sectors)))

    def set_img_track(self, tdat: bytes) -> int:
        pos = 0
        self.sectors.sort(key = lambda x: x.idam.r)
        if self.img_bps is not None:
            totsize = len(self.sectors) * self.img_bps
        else:
            totsize = functools.reduce(lambda x, y: x + len(y.dam.data),
                                       self.sectors, 0)
        if len(tdat) < totsize:
            tdat += bytes(totsize - len(tdat))
        for s in self.sectors:
            s.crc = s.idam.crc = s.dam.crc = 0
            size = len(s.dam.data)
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
        readback_track.decode_flux(flux)
        if readback_track.nr_missing() != 0:
            return False
        return self.sectors == readback_track.sectors

    def mfm_master_track(self) -> bytes:

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

    def fm_master_track(self, mmfm_areas=None) -> bytes:

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
                t += sync(dam[0])
                if ((dam[0] & 0xfb) == Mark.DDAM_DEC_MMFM
                    and mmfm_areas is not None):
                    mmfm_areas.append((dec_mmfm.encode(dam[1:]), len(t)))
                    t += encode(bytes([self.gapbyte] * (128+2)))
                else:
                    t += encode(dam[1:])

        return t

    def master_track(self) -> MasterTrack:

        t: Union[bytes, bitarray]

        if self.mode is Mode.FM:
            t = self.fm_master_track()
        elif self.mode is Mode.MFM:
            t = self.mfm_master_track()
        elif self.mode is Mode.DEC_RX02:
            mmfm_areas: List[Tuple[bytes,int]] = list()
            t = self.fm_master_track(mmfm_areas)

        # Add the pre-index gap.
        tlen = int((self.time_per_rev / self.clock) // 16)
        gap = max(tlen - len(t)//2, 0)
        t += encode(bytes([self.gapbyte] * gap))

        if self.mode is Mode.FM:
            t = fm_encode(t)
        elif self.mode is Mode.MFM:
            t = mfm_encode(t)
        elif self.mode is Mode.DEC_RX02:
            # Insert the MMFM areas into the doubled-rate FM track
            b = bytearray(doubler(fm_encode(t)))
            for a,o in mmfm_areas:
                b[2*o:2*(o+256+2)] = a
            # Insert the extra clock at the start of each MMFM area
            bits = bitarray(endian='big')
            bits.frombytes(b)
            for _,o in reversed(mmfm_areas):
                bits.insert(16*o, 0)
            # We pass a bitarray to MasterTrack()
            t = bits

        track = MasterTrack(
            bits = t,
            time_per_rev = self.time_per_rev)
        track.verify = self
        return track

    @staticmethod
    def mfm_decode_raw(raw: PLLTrack) -> List[TrackArea]:

        bits, _ = raw.get_all_data()
        areas: List[TrackArea] = []
        idam = None

        ## 1. Calculate offsets within dump
        
        for offs in bits.search(mfm_iam_sync):
            if len(bits) < offs+4*16:
                continue
            mark = decode(bits[offs+3*16:offs+4*16].tobytes())[0]
            if mark == Mark.IAM:
                areas.append(IAM(offs, offs+4*16))

        for offs in bits.search(mfm_sync):

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
                if idam is None or offs - idam.end > 1000:
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
                print("Unknown mark %02x" % mark)

        if idam is not None:
            areas.append(idam)

        # Convert to offsets within track
        areas.sort(key=lambda x:x.start)
        index = iter([x.nr_bits for x in raw.revolutions])
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

    @staticmethod
    def fm_decode_raw(raw: PLLTrack,
                      mmfm_raw: Optional[PLLTrack] = None) -> List[TrackArea]:

        bits, times = raw.get_all_data()
        areas: List[TrackArea] = []
        idam = None

        if mmfm_raw is not None:
            mmfm_bits, mmfm_times = mmfm_raw.get_all_data()
            mmfm_iter = mmfm_bits.search(dec_mmfm.sync_prefix)
            mmfm_offs = next(mmfm_iter, None)
            fm_time, prev_fm_offs = 0.0, 0
            mmfm_time, prev_mmfm_offs = 0.0, 0

        ## 1. Calculate offsets within dump
        
        for offs in bits.search(fm_iam_sync):
            offs += 16
            areas.append(IAM(offs, offs+1*16))

        for offs in bits.search(fm_sync_prefix):

            # DEC MMFM track: Ensure this looks like an FM mark even at
            # double rate. This also finds the equivalent point in the
            # double-rate bitstream.
            if mmfm_raw is not None:
                fm_time += sum(times[prev_fm_offs:offs])
                prev_fm_offs = offs
                while mmfm_offs is not None:
                    mmfm_time += sum(mmfm_times[prev_mmfm_offs:mmfm_offs])
                    prev_mmfm_offs = mmfm_offs
                    delta = fm_time - mmfm_time
                    if delta < 1e-5:
                        break
                    mmfm_offs = next(mmfm_iter, None)
                # We require a match within 10us in the double-rate bitstream.
                if mmfm_offs is None or abs(delta) > 1e-5:
                    continue

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
            elif (mark == Mark.DAM or mark == Mark.DDAM
                  or mark == Mark.DAM_TRS80_DIR
                  or ((mark & 0xfb) == Mark.DDAM_DEC_MMFM
                      and mmfm_raw is not None)):
                if idam is None or offs - idam.end > 1000:
                    areas.append(DAM(offs, offs+4*16, 0xffff, mark=mark))
                    continue
                sz = 128 << idam.n
                s, e = offs, offs+(1+sz+2)*16
                if (mark & 0xfb) != Mark.DDAM_DEC_MMFM:
                    if len(bits) < e:
                        continue
                    b = decode(bits[s:e].tobytes())
                else:
                    assert mmfm_offs is not None
                    ds, de = mmfm_offs+64+1, mmfm_offs+64+1+(sz*2+2)*16
                    if len(mmfm_bits) < de:
                        continue
                    b = bytes([mark]) + dec_mmfm.decode(mmfm_bits[ds:de])
                crc = crc16.new(b).crcValue
                dam = DAM(s, e, crc, mark=mark, data=b[1:-2])
                areas.append(Sector(idam, dam))
                idam = None
            else:
                print("Unknown mark %02x" % mark)

        if idam is not None:
            areas.append(idam)

        # Convert to offsets within track
        areas.sort(key=lambda x:x.start)
        index = iter([x.nr_bits for x in raw.revolutions])
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

    def decode_flux(self, track: HasFlux, pll: Optional[PLL]=None) -> None:
        flux = track.flux()
        flux.cue_at_index()
        raw = PLLTrack(time_per_rev = self.time_per_rev,
                       clock = self.clock, data = flux, pll = pll)
        self.decode_raw(raw, pll, flux)

    def decode_raw(self, raw: PLLTrack, pll: Optional[PLL],
                   flux: Flux) -> None:

        if self.mode is Mode.FM:
            areas = self.fm_decode_raw(raw)
        elif self.mode is Mode.MFM:
            areas = self.mfm_decode_raw(raw)
        elif self.mode is Mode.DEC_RX02:
            mmfm_raw = PLLTrack(time_per_rev = self.time_per_rev,
                                clock = self.clock/2, data = flux, pll = pll)
            areas = self.fm_decode_raw(raw, mmfm_raw)

        # Add to the deduped lists
        for a in areas:
            dupe = False
            if isinstance(a, IAM):
                for iam in self.iams:
                    if dupe := abs(iam.start - a.start) < 1000:
                        break
                if not dupe:
                    self.iams.append(a)
            elif isinstance(a, Sector):
                for i, sec in enumerate(self.sectors):
                    if dupe := abs(sec.start - a.start) < 1000:
                        if sec.crc != 0 and a.crc == 0:
                            self.sectors[i] = a
                        break
                if not dupe:
                    self.sectors.append(a)
        self.iams.sort(key=lambda x:x.start)
        self.sectors.sort(key=lambda x:x.start)


class IBMTrack_Fixed(IBMTrack):

    def __init__(self, cyl: int, head: int, mode: Mode):
        super().__init__(cyl, head, mode)
        self.raw = IBMTrack(cyl, head, mode)
        self.oversized = False

    def decode_flux(self, track: HasFlux, pll: Optional[PLL]=None) -> None:
        self.raw.clock = self.clock
        self.raw.time_per_rev = self.time_per_rev
        self.raw.decode_flux(track, pll)
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
                        s.dam.mark = r.dam.mark
            if not matched:
                mismatches.add((r.idam.c, r.idam.h, r.idam.r, r.idam.n))
        for m in mismatches:
            print('T%d.%d: Ignoring unexpected sector C:%d H:%d R:%d N:%d'
                  % (self.cyl, self.head, *m))

    @classmethod
    def from_config(cls, config: IBMTrack_FixedDef, cyl: int, head: int,
                    warn_on_oversize = True):

        def sec_n(i):
            return config.sz[i] if i < len(config.sz) else config.sz[-1]

        if config.format_name == 'dec.rx02':
            mode, gaps, mark_dam = Mode.DEC_RX02, FMGaps, Mark.DAM_DEC_MMFM
            synclen = 1 # Mark
        elif config.format_name == 'ibm.mfm':
            mode, gaps, mark_dam = Mode.MFM, MFMGaps, Mark.DAM
            synclen = 4 # A1 A1 A1 Mark
        elif config.format_name == 'ibm.fm':
            mode, gaps, mark_dam = Mode.FM, FMGaps, Mark.DAM
            synclen = 1 # Mark

        t = cls(cyl, head, mode)
        nsec = config.secs
        t.img_bps = config.img_bps

        if config.gapbyte is not None:
            t.gapbyte = config.gapbyte

        if config.iam:
            gap1 = gaps.gap1 if config.gap1 is None else config.gap1
        else:
            gap1 = None
        gap2 = gaps.gap2 if config.gap2 is None else config.gap2
        gap3 = 0 if config.gap3 is None else config.gap3
        gap4a = gaps.gap4a if config.gap4a is None else config.gap4a

        idx_sz = gap4a
        if gap1 is not None:
            idx_sz += t.gap_presync + synclen + gap1
        idam_sz = t.gap_presync + synclen + 4 + 2 + gap2
        dam_sz_pre = t.gap_presync + synclen
        dam_sz_post = 2 + gap3

        tracklen = idx_sz + (idam_sz + dam_sz_pre + dam_sz_post) * nsec
        for i in range(nsec):
            tracklen += 128 << sec_n(i)
        tracklen *= 16

        rate, rpm = config.rate, config.rpm
        if rate == 0:
            # FM: 0 = Micro-diskette (125kbps), 1 = 8-inch disk (250kbps)
            # MFM: 1 = DD (250kbps), 2 = HD (500kbps), 3 = ED (1000kbps)
            for i in (range(2),range(1,4))[mode is Mode.MFM]:
                maxlen = (50000*300//rpm) << i
                maxlen += maxlen * 3 // 100 # Allow a few percent overage
                if tracklen < maxlen:
                    break
            rate = 125 << i

        if mode is Mode.MFM and config.gap2 is None and rate >= 1000:
            # At ED rate the default GAP2 is 41 bytes.
            gap2 = 41
            idam_sz += gap2 - gaps.gap2
            tracklen += 16 * nsec * (gap2 - gaps.gap2)

        tracklen_bc = rate * 400 * 300 // rpm

        # Calculate a sensible gap3 value if none is manually specified
        if nsec != 0 and config.gap3 is None:
            space = max(0, tracklen_bc - tracklen)
            no = sec_n(0)
            gap3 = min(space // (16*nsec), gaps.gap3[no])
            dam_sz_post += gap3
            tracklen += 16 * nsec * gap3

        # Allow for at least 1% pre-index gap, including final gap3
        pre_index_sz = tracklen_bc // 100
        if nsec != 0:
            pre_index_sz = max(0, pre_index_sz - gap3 * 16)
        tracklen += pre_index_sz

        # Steal some post-index gap if there is insufficient pre-index gap
        if tracklen > tracklen_bc and config.gap4a is None:
            new_gap4a = gap4a // 2
            idx_sz -= gap4a - new_gap4a
            tracklen -= gap4a - new_gap4a
            gap4a = new_gap4a

        if tracklen > tracklen_bc * 105//100:
            t.oversized = True
            if warn_on_oversize:
                print('T%d.%d: IBM: WARNING: Track is %.2f%% too long'
                      % (cyl, head, 100.0*tracklen/tracklen_bc))
        tracklen_bc = max(tracklen_bc, tracklen)

        t.time_per_rev = 60 / rpm
        t.clock = t.time_per_rev / tracklen_bc

        pos = gap4a
        if gap1 is not None:
            pos += t.gap_presync
            t.iams = [IAM(pos*16,(pos+synclen)*16)]
            pos += synclen + gap1

        id0 = config.id
        h = head if config.h is None else config.h
        for sec in sec_map(nsec, config.interleave,
                           config.cskew, config.hskew, cyl, head):
            pos += t.gap_presync
            idam = IDAM(pos*16, (pos+synclen+4+2)*16, 0xffff,
                        c = cyl, h = h, r = id0+sec, n = sec_n(sec))
            pos += synclen + 4 + 2 + gap2 + t.gap_presync
            size = 128 << idam.n
            datsz = size*2 if mark_dam == Mark.DAM_DEC_MMFM else size
            dam = DAM(pos*16, (pos+synclen+size+2)*16, 0xffff,
                      mark=mark_dam, data=b'-=[BAD SECTOR]=-'*(datsz//16))
            t.sectors.append(Sector(idam, dam))
            pos += synclen + size + 2 + gap3

        return t


class IBMTrack_FixedDef(codec.TrackDef):

    default_revs = default_revs

    def __init__(self, format_name: str):
        self.secs = 0
        self.sz: List[int] = []
        self.id = 1
        self.h: Optional[int] = None
        self.format_name = format_name
        self.interleave = 1
        self.cskew, self.hskew = 0, 0
        self.rpm = 300
        self.gap1: Optional[int] = None
        self.gap2: Optional[int] = None
        self.gap3: Optional[int] = None
        self.gap4a: Optional[int] = None
        self.gapbyte: Optional[int] = None
        self.iam = True
        self.rate = 0
        self.img_bps: Optional[int] = None
        self.finalised = False

    def add_param(self, key: str, val: str) -> None:
        if key == 'secs':
            n = int(val)
            error.check(0 <= n <= 256, '%s out of range' % key)
            self.secs = n
        elif key == 'bps':
            self.sz = []
            for x in val.split(','):
                y = re.match(r'(\d+)\*(\d+)', x)
                if y is not None:
                    n, l = int(y.group(1)), int(y.group(2))
                else:
                    n, l = int(x), 1
                s = 0
                while n != 128<<s:
                    s += 1
                    error.check(s <= 6, 'bps value out of range')
                for _ in range(l):
                    self.sz.append(s)
        elif key == 'interleave':
            n = int(val)
            error.check(1 <= n <= 255, '%s out of range' % key)
            self.interleave = n
        elif key in ['id', 'cskew', 'hskew']:
            n = int(val, base=0)
            error.check(0 <= n <= 255, '%s out of range' % key)
            setattr(self, key, n)
        elif key in ['gap1', 'gap2', 'gap3', 'gap4a', 'gapbyte', 'h']:
            if val == 'auto':
                n = None
            else:
                n = int(val, base=0)
                error.check(0 <= n <= 255, '%s out of range' % key)
            setattr(self, key, n)
        elif key == 'iam':
            error.check(val in ['yes', 'no'], 'bad iam value')
            self.iam = val == 'yes'
        elif key in ['rate', 'rpm']:
            n = int(val)
            error.check(1 <= n <= 2000, '%s out of range' % key)
            setattr(self, key, n)
        elif key == 'img_bps':
            n = int(val)
            error.check(128 <= n <= 8192, '%s out of range' % key)
            self.img_bps = n
        else:
            raise error.Fatal('unrecognised track option %s' % key)

    def finalise(self) -> None:
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

    def mk_track(self, cyl: int, head: int) -> IBMTrack_Fixed:
        return IBMTrack_Fixed.from_config(self, cyl, head)


class IBMTrack_Empty(IBMTrack):

    def __init__(self, cyl, head):
        # Fake some parameters for master_track()
        super().__init__(cyl, head, Mode.MFM)
        self.time_per_rev = 0.2
        self.clock = 2e-6

    def summary_string(self) -> str:
        return "IBM Empty"

    def set_img_track(self, tdat: bytes) -> int:
        raise error.Fatal('ibm.scan: Cannot handle IMG input data')


class IBMTrack_Scan(codec.Codec):

    RATES = [ 125, 250, 500 ]
    RPMS = [ 300, 360 ]
    BEST_GUESS = None
    
    def __init__(self, cyl: int, head: int, config: IBMTrack_ScanDef):
        self.cyl, self.head = cyl, head
        self.rate, self.rpm = config.rate, config.rpm
        self.track: IBMTrack = IBMTrack_Empty(cyl, head)

    @property
    def nsec(self) -> int:
        return self.track.nsec

    def summary_string(self) -> str:
        return self.track.summary_string()

    def has_sec(self, sec_id: int):
        return self.track.has_sec(sec_id)

    def nr_missing(self) -> int:
        return self.track.nr_missing()

    def master_track(self) -> MasterTrack:
        return self.track.master_track()

    def set_img_track(self, tdat: bytes) -> int:
        return self.track.set_img_track(tdat)

    def get_img_track(self) -> bytearray:
        return self.track.get_img_track()

    def decode_flux(self, track: HasFlux, pll: Optional[PLL]=None) -> None:

        # Add more data to an existing track instance?
        if not isinstance(self.track, IBMTrack_Empty):
            self.track.decode_flux(track, pll)
            return

        # Try our best guess first.
        if IBMTrack_Scan.BEST_GUESS is not None:
            time_per_rev, clock, mode = IBMTrack_Scan.BEST_GUESS
            t = IBMTrack(self.cyl, self.head, mode)
            t.clock, t.time_per_rev = clock, time_per_rev
            t.decode_flux(track, pll)
            # Perfect match, no missing sectors? 
            if t.nsec != 0 and t.nr_missing() == 0:
                self.track = t
                return

        rates = self.RATES if self.rate is None else [self.rate]
        rpms = self.RPMS if self.rpm is None else [self.rpm]

        flux = track.flux()
        flux.cue_at_index()

        # Scan at various rates & modes to find at least one sector
        for rpm in rpms:
            time_per_rev = 60 / rpm
            for rate in rates:
                clock = 5e-4 / rate
                raw = PLLTrack(time_per_rev = time_per_rev,
                               clock = clock, data = flux, pll = pll)
                for mode in [Mode.MFM, Mode.FM]:
                    t = IBMTrack(self.cyl, self.head, mode)
                    t.clock, t.time_per_rev = clock, time_per_rev
                    t.decode_raw(raw, pll, flux)
                    if ((t.nsec - t.nr_missing())
                        > (self.track.nsec - self.track.nr_missing())):
                        self.track = t

        # If we found a match, remember it as a best guess for the next track.
        if not isinstance(self.track, IBMTrack_Empty):
            t = self.track
            IBMTrack_Scan.BEST_GUESS = (t.time_per_rev, t.clock, t.mode)


class IBMTrack_ScanDef(codec.TrackDef):

    default_revs = default_revs

    def __init__(self, format_name: str):
        self.rpm: Optional[int] = None
        self.rate: Optional[int] = None

    def add_param(self, key: str, val: str) -> None:
        if key in ['rate', 'rpm']:
            n = int(val)
            error.check(1 <= n <= 2000, '%s out of range' % key)
            setattr(self, key, n)
        else:
            raise error.Fatal('unrecognised track option %s' % key)

    def finalise(self) -> None:
        pass

    def mk_track(self, cyl: int, head: int) -> IBMTrack_Scan:
        return IBMTrack_Scan(cyl, head, self)

# Local variables:
# python-indent: 4
# End:
