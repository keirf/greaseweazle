# greaseweazle/codec/ibm/fm.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from typing import List, Optional

import copy, heapq, struct, functools
import itertools as it
from bitarray import bitarray
import crcmod.predefined

from greaseweazle.track import MasterTrack, RawTrack
from .ibm import TrackArea, IDAM, DAM, Sector, IAM, IBMTrack
from .mfm import decode

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

class IBM_FM(IBMTrack):

    gap_presync = 6

    gapbyte = 0xff

    def summary_string(self) -> str:
        nsec, nbad = len(self.sectors), self.nr_missing()
        s = "IBM FM (%d/%d sectors)" % (nsec - nbad, nsec)
        return s


    def decode_raw(self, track, pll=None) -> None:
        flux = track.flux()
        flux.cue_at_index()
        raw = RawTrack(time_per_rev = self.time_per_rev,
                       clock = self.clock, data = flux, pll = pll)
        bits, _ = raw.get_all_data()

        areas: List[TrackArea] = []
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
                    n += next(index)
                except StopIteration:
                    n = float('inf')
            a.delta(p)
        areas.sort(key=lambda x:x.start)

        # Add to the deduped lists
        self.add_deduped_areas(areas)


    def raw_track(self) -> MasterTrack:

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

    def __init__(self, cyl: int, head: int):
        super().__init__(cyl, head)
        self.raw_iams: List[IAM] = []
        self.raw_sectors: List[Sector] = []
        self.img_bps: Optional[int] = None

    def decode_raw(self, track, pll=None) -> None:
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
        readback_track = IBM_FM_Formatted(self.cyl, self.head)
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

    GAP_1  = 26 # Post-IAM
    GAP_2  = 11 # Post-IDAM
    GAP_3  = [ 27, 42, 58, 138, 255, 255, 255, 255 ]

    @classmethod
    def from_config(cls, config, cyl, head):

        def sec_n(i):
            return config.sz[i] if i < len(config.sz) else config.sz[-1]

        t = cls(cyl, head)
        t.nsec = nsec = config.secs
        t.img_bps = config.img_bps

        if config.iam:
            gap_1 = t.GAP_1 if config.gap1 is None else config.gap1
        else:
            gap_1 = None
        gap_2 = t.GAP_2 if config.gap2 is None else config.gap2
        gap_3 = 0 if config.gap3 is None else config.gap3
        if config.gap4a is None:
            gap_4a = 40 if config.iam else 16
        else:
            gap_4a = config.gap4a

        idx_sz = gap_4a
        if gap_1 is not None:
            idx_sz += t.gap_presync + 1 + gap_1
        idam_sz = t.gap_presync + 5 + 2 + gap_2
        dam_sz_pre = t.gap_presync + 1
        dam_sz_post = 2 + gap_3

        tracklen = idx_sz + (idam_sz + dam_sz_pre + dam_sz_post) * nsec
        for i in range(nsec):
            tracklen += 128 << sec_n(i)
        tracklen *= 16

        rate, rpm = config.rate, config.rpm
        if rate == 0:
            # Micro-diskette = 125kbps, 8-inch disk = 250kbps
            for i in range(2): # 0=125kbps, 1=250kbps
                maxlen = ((50000*300//rpm) << i) + 5000
                if tracklen < maxlen:
                    break
            rate = 125 << i # 125kbps or 250kbps

        tracklen_bc = rate * 400 * 300 // rpm

        if nsec != 0 and config.gap3 is None:
            space = max(0, tracklen_bc - tracklen)
            no = sec_n(0)
            gap_3 = min(space // (16*nsec), t.GAP_3[no])
            dam_sz_post += gap_3
            tracklen += 16 * nsec * gap_3

        tracklen_bc = max(tracklen_bc, tracklen)

        t.time_per_rev = 60 / rpm
        t.clock = t.time_per_rev / tracklen_bc

        # Create logical sector map in rotational order
        sec_map, pos = [-1] * nsec, 0
        if nsec != 0:
            pos = (cyl*config.cskew + head*config.hskew) % nsec
        for i in range(nsec):
            while sec_map[pos] != -1:
                pos = (pos + 1) % nsec
            sec_map[pos] = i
            pos = (pos + config.interleave) % nsec

        pos = gap_4a
        if gap_1 is not None:
            pos += t.gap_presync
            t.iams = [IAM(pos*16,(pos+1)*16)]
            pos += 1 + gap_1

        id0 = config.id
        h = head if config.h is None else config.h
        for i in range(nsec):
            sec = sec_map[i]
            pos += t.gap_presync
            idam = IDAM(pos*16, (pos+7)*16, 0xffff,
                        c = cyl, h = h, r= id0+sec, n = sec_n(sec))
            pos += 7 + gap_2 + t.gap_presync
            size = 128 << idam.n
            dam = DAM(pos*16, (pos+1+size+2)*16, 0xffff,
                      mark=t.DAM, data=b'-=[BAD SECTOR]=-'*(size//16))
            t.sectors.append(Sector(idam, dam))
            pos += 1 + size + 2 + gap_3

        return t


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


# Local variables:
# python-indent: 4
# End:
