# greaseweazle/codec/heathkit/h17.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

# Useful notes:
# https://sebhc.github.io/sebhc/project8080/design_h17.html

import binascii

import struct
import itertools as it
from bitarray import bitarray

from greaseweazle.track import MasterTrack, RawTrack

from greaseweazle.codec.ibm import fm

default_revs = 1.1

# 00 00 FD: recorded LSB first and FM encoded.
sync_bytes = b'\xaa\xaa\xaa\xaa\xef\xff'
sync = bitarray(endian='big')
sync.frombytes(sync_bytes)

bad_sector = b'-=[BAD SECTOR]=-' * 16

class Heathkit_H17:

    nsec = 10
    clock = 4e-6
    time_per_rev = 0.2

    def __init__(self, cyl, head):
        self.cyl, self.head = cyl, head
        self.sector = [None] * self.nsec
        self.map = [None] * self.nsec

    def summary_string(self):
        nsec, nbad = self.nsec, self.nr_missing()
        s = "Heathkit H17 (%d/%d sectors)" % (nsec - nbad, nsec)
        return s

    # private
    def exists(self, sec_id, pos):
        return ((self.sector[sec_id] is not None)
                or (self.map[pos] is not None))

    # private
    def add(self, sec_id, data):
        if self.exists(sec_id, sec_id):
            return
        self.sector[sec_id] = data
        self.map[sec_id] = sec_id

    def has_sec(self, sec_id):
        return self.sector[sec_id] is not None

    def nr_missing(self):
        return len([sec for sec in self.sector if sec is None])

    def get_img_track(self):
        tdat = bytearray()
        for sec in self.sector:
            tdat += sec if sec is not None else bad_sector
        return tdat

    def set_img_track(self, tdat):
        totsize = self.nsec * 512
        if len(tdat) < totsize:
            tdat += bytes(totsize - len(tdat))
        self.map = list(range(self.nsec))
        for sec in self.map:
            self.sector[sec] = tdat[sec*512:(sec+1)*512]
        return totsize

    def flux(self, *args, **kwargs):
        return self.raw_track().flux(*args, **kwargs)


    def decode_raw(self, track):
        flux = track.flux()
        flux.index_list = [0.2*flux.sample_freq]
#        if len(flux.index_list) >= self.nsec:
#            thresh = sum(flux.index_list) / len(flux.index_list)
#            print(thresh/flux.sample_freq)

        raw = RawTrack(time_per_rev = self.time_per_rev,
                       clock = self.clock, data = flux)
        bits, _ = raw.get_all_data()

        idx = 0
        while True:
            offs = bits.find(sync, idx)
            if offs < 0:
                break
            idx = offs + 1

            hdr = bits[offs:offs+7*16].tobytes()
            if len(hdr) != 14:
                continue
            hdr = decode(hdr)
            if checksum(hdr[3:]) != 0:
                continue

            vol, trk, sec_id = hdr[3:6]
            if trk != self.cyl or sec_id >= self.nsec:
                continue

            offs = bits.find(sync, idx + 7*16, idx + 100*16)
            if offs < 0:
                continue
            sec = bits[offs:offs+(3+256+1)*16].tobytes()
            if len(sec) != (3+256+1)*2:
                continue
            sec = decode(sec)
            if checksum(sec[3:]) != 0:
                continue
            self.add(sec_id, sec[3:-1])
            idx = offs + (3+256+1)*16


    def raw_track(self):

        # List of sector IDs missing from the sector map:
        missing = iter([x for x in range(self.nsec) if not x in self.map])
        # Sector map with the missing entries filled in:
        full_map = [next(missing) if x is None else x for x in self.map]

        t = bytes()

        for nr, sec_id in zip(range(self.nsec), full_map):
            sector = self.sector[sec_id]
            data = bad_sector if sector is None else sector
            header = bytes([0, self.cyl, sec_id])
            t += encode(bytes(14)) + sync_bytes
            t += encode(header) + encode(bytes([checksum(header)]))
            t += encode(bytes(14)) + sync_bytes
            t += encode(data) + encode(bytes([checksum(data)]))
            t += encode(bytes(16))

        # Add the pre-index gap.
        tlen = int((self.time_per_rev / self.clock) // 16)
        gap = max(tlen - len(t)//2, 0)
        t += encode(bytes(gap))

        track = MasterTrack(
            bits = t,
            time_per_rev = 0.2)
        track.verify = self
        track.verify_revs = default_revs
        return track


    def verify_track(self, flux):
        cyl = self.tracknr // 2
        head = self.tracknr & 1
        readback_track = self.decode_track(cyl, head, flux)
        return (readback_track.nr_missing() == 0
                and self.sector == readback_track.sector)

    @classmethod
    def decode_track(cls, cyl, head, track):
        ados = cls(cyl, head)
        ados.decode_raw(track)
        return ados

def bitrev(dat):
    out = bytearray()
    for x in dat:
        y = 0
        for i in range(8):
            y <<= 1
            y |= x&1
            x >>= 1
        out.append(y)
    return out

def encode(dat):
    return fm.encode(bitrev(dat))

def decode(dat):
    return bitrev(fm.decode(dat))

def checksum(dat):
    y = 0
    for x in dat:
        y ^= x
        y = (y>>7) | ((y&127)<<1)
    return y


# Local variables:
# python-indent: 4
# End:
