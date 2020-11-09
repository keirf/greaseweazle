# greaseweazle/codec/amiga/amigados.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import struct
import itertools as it
from bitarray import bitarray

from greaseweazle.bitcell import Bitcell

sync_bytes = b'\x44\x89\x44\x89'
sync = bitarray(endian='big')
sync.frombytes(sync_bytes)

class AmigaDOS:

    DDSEC = 11

    def __init__(self, tracknr, nsec=DDSEC):
        self.tracknr = tracknr
        self.nsec = nsec
        self.sector = [None] * nsec
        self.map = [None] * nsec

    def exists(self, sec_id, togo):
        return ((self.sector[sec_id] is not None)
                or (self.map[self.nsec-togo] is not None))

    def nr_missing(self):
        return len([sec for sec in self.sector if sec is None])

    def add(self, sec_id, togo, label, data):
        assert not self.exists(sec_id, togo)
        self.sector[sec_id] = label, data
        self.map[self.nsec-togo] = sec_id

    def get_adf_track(self):
        tdat = bytearray()
        for sec in self.sector:
            tdat += sec[1] if sec is not None else bytes([0] * 512)
        return tdat

    def set_adf_track(self, tdat):
        self.map = list(range(self.nsec))
        for sec in self.map:
            self.sector[sec] = bytes([0x00] * 16), tdat[sec*512:(sec+1)*512]

    def flux_for_writeout(self):
        return self.flux()

    def flux(self):
        return self

    def bits(self):
        next_bad_sec_id = 0
        t = bytearray(64)
        for nr in range(self.nsec):
            sec_id = self.map[nr]
            if sec_id is None:
                while self.sector[next_bad_sec_id] is not None:
                    next_bad_sec_id += 1
                sec_id = next_bad_sec_id
                label, data = bytes([0x00] * 16), bytes([0x00] * 512)
            else:
                label, data = self.sector[sec_id]
            t += sync_bytes
            header = bytes([0xff, self.tracknr, sec_id, self.nsec-nr])
            t += encode(header)
            t += encode(label)
            t += encode(struct.pack('>I', checksum(header + label)))
            t += encode(struct.pack('>I', checksum(data)))
            t += encode(data)
            t += encode([0x00] * 2)
        tlen = 101376 if self.nsec == 11 else 202752
        t += bytes(tlen//8-len(t))
        return mfm_encode(t)

    def verify_track(self, flux):
        cyl = self.tracknr // 2
        head = self.tracknr & 1
        readback_track = decode_track(cyl, head, flux)
        return readback_track.nr_missing() == 0

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
    
def encode(dat):
    return bytes(it.chain(map(lambda x: (x >> 1) & 0x55, dat),
                          map(lambda x: x & 0x55, dat)))

def decode(dat):
    length = len(dat)//2
    return bytes(map(lambda x, y: (x << 1 & 0xaa) | (y & 0x55),
                     it.islice(dat, 0, length),
                     it.islice(dat, length, None)))

def checksum(dat):
    csum = 0
    for i in range(0, len(dat), 4):
        csum ^= struct.unpack('>I', dat[i:i+4])[0]
    return (csum ^ (csum>>1)) & 0x55555555

def decode_track(cyl, head, flux):

    bc = Bitcell(clock = 2e-6, flux = flux)
    bits, times = bc.bitarray, bc.timearray
    tracknr = cyl*2 + head
    ados = AmigaDOS(tracknr)
    
    sectors = bits.search(sync)
    for offs in bits.itersearch(sync):
        sec = bits[offs:offs+544*16].tobytes()
        header = decode(sec[4:12])
        format, track, sec_id, togo = tuple(header)
        if format != 0xff or track != tracknr \
           or not(sec_id < ados.nsec and 0 < togo <= ados.nsec) \
           or ados.exists(sec_id, togo):
            continue

        label = decode(sec[12:44])
        hsum, = struct.unpack('>I', decode(sec[44:52]))
        if hsum != checksum(header + label):
            continue

        dsum, = struct.unpack('>I', decode(sec[52:60]))
        data = decode(sec[60:1084])
        gap = decode(sec[1084:1088])
        if dsum != checksum(data):
            continue;

        ados.add(sec_id, togo, label, data)
        if ados.nr_missing() == 0:
            break

    return ados


# Local variables:
# python-indent: 4
# End:
