# greaseweazle/codec/amiga/amigados.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import struct
import itertools as it
from bitarray import bitarray

from greaseweazle.track import MasterTrack, RawTrack

default_trackset = 'c=0-79:h=0-1'
default_revs = 1.1

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

    def summary_string(self):
        return ("AmigaDOS (%d/%d sectors)"
                % (self.nsec - self.nr_missing(), self.nsec))

    # private
    def exists(self, sec_id, togo):
        return ((self.sector[sec_id] is not None)
                or (self.map[self.nsec-togo] is not None))

    # private
    def add(self, sec_id, togo, label, data):
        assert not self.exists(sec_id, togo)
        self.sector[sec_id] = label, data
        self.map[self.nsec-togo] = sec_id

    def has_sec(self, sec_id):
        return self.sector[sec_id] is not None

    def nr_missing(self):
        return len([sec for sec in self.sector if sec is None])

    def get_adf_track(self):
        tdat = bytearray()
        for sec in self.sector:
            tdat += sec[1] if sec is not None else bytes(512)
        return tdat

    def set_adf_track(self, tdat):
        self.map = list(range(self.nsec))
        for sec in self.map:
            self.sector[sec] = bytes(16), tdat[sec*512:(sec+1)*512]

    def flux_for_writeout(self, *args, **kwargs):
        return self.raw_track().flux_for_writeout(args, kwargs)

    def flux(self, *args, **kwargs):
        return self.raw_track().flux(args, kwargs)


    def decode_raw(self, track):
        raw = RawTrack(clock = 2e-6, data = track)
        bits, _ = raw.get_all_data()

        for offs in bits.itersearch(sync):

            if self.nr_missing() == 0:
                break

            sec = bits[offs:offs+544*16].tobytes()
            if len(sec) != 1088:
                continue

            header = decode(sec[4:12])
            format, track, sec_id, togo = tuple(header)
            if format != 0xff or track != self.tracknr \
               or not(sec_id < self.nsec and 0 < togo <= self.nsec) \
               or self.exists(sec_id, togo):
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

            self.add(sec_id, togo, label, data)


    def raw_track(self):

        # List of sector IDs missing from the sector map:
        missing = iter([x for x in range(self.nsec) if not x in self.map])
        # Sector map with the missing entries filled in:
        full_map = [next(missing) if x is None else x for x in self.map]

        # Post-index track gap.
        t = encode(bytes(128 * (self.nsec//11)))

        for nr, sec_id in zip(range(self.nsec), full_map):
            sector = self.sector[sec_id]
            label, data = (bytes(16), bytes(512)) if sector is None else sector
            header = bytes([0xff, self.tracknr, sec_id, self.nsec-nr])
            t += sync_bytes
            t += encode(header)
            t += encode(label)
            t += encode(struct.pack('>I', checksum(header + label)))
            t += encode(struct.pack('>I', checksum(data)))
            t += encode(data)
            t += encode(bytes(2))

        # Add the pre-index gap.
        tlen = 101376 * (self.nsec//11)
        t += bytes(tlen//8-len(t))

        track = MasterTrack(
            bits = mfm_encode(t),
            time_per_rev = 0.2)
        track.verify = self
        track.verify_revs = default_revs
        return track


    def verify_track(self, flux):
        cyl = self.tracknr // 2
        head = self.tracknr & 1
        readback_track = decode_track(cyl, head, flux)
        return (readback_track.nr_missing() == 0
                and self.sector == readback_track.sector)


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


def decode_track(cyl, head, track):
    ados = AmigaDOS(cyl*2 + head)
    ados.decode_raw(track)
    return ados


# Local variables:
# python-indent: 4
# End:
