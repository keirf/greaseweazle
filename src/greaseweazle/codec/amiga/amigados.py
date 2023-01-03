# greaseweazle/codec/amiga/amigados.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import struct
import itertools as it
from bitarray import bitarray

from greaseweazle import error
from greaseweazle.track import MasterTrack, RawTrack

default_revs = 1.1

sync_bytes = b'\x44\x89\x44\x89'
sync = bitarray(endian='big')
sync.frombytes(sync_bytes)

bad_sector = b'-=[BAD SECTOR]=-' * 32

class AmigaDOS:

    time_per_rev = 0.2

    def __init__(self, cyl, head):
        self.tracknr = cyl*2 + head
        self.sector = [None] * self.nsec
        self.map = [None] * self.nsec

    def summary_string(self):
        nsec, nbad = self.nsec, self.nr_missing()
        s = "AmigaDOS (%d/%d sectors)" % (nsec - nbad, nsec)
        return s

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

    def get_img_track(self):
        tdat = bytearray()
        for sec in self.sector:
            tdat += sec[1] if sec is not None else bad_sector
        return tdat

    def set_img_track(self, tdat):
        totsize = self.nsec * 512
        if len(tdat) < totsize:
            tdat += bytes(totsize - len(tdat))
        self.map = list(range(self.nsec))
        for sec in self.map:
            self.sector[sec] = bytes(16), tdat[sec*512:(sec+1)*512]
        return totsize

    def flux(self, *args, **kwargs):
        return self.raw_track().flux(*args, **kwargs)


    def decode_raw(self, track, pll=None):
        raw = RawTrack(time_per_rev = self.time_per_rev,
                       clock = self.clock, data = track, pll = pll)
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
            label, data = (bytes(16), bad_sector) if sector is None else sector
            header = bytes([0xff, self.tracknr, sec_id, self.nsec-nr])
            t += sync_bytes
            t += encode(header)
            t += encode(label)
            t += encode(struct.pack('>I', checksum(header + label)))
            t += encode(struct.pack('>I', checksum(data)))
            t += encode(data)
            t += encode(bytes(2))

        # Add the pre-index gap.
        tlen = (int((self.time_per_rev / self.clock)) + 31) & ~31
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
        readback_track = self.decode_track(cyl, head, flux)
        return (readback_track.nr_missing() == 0
                and self.sector == readback_track.sector)

    @classmethod
    def decode_track(cls, cyl, head, track):
        ados = cls(cyl, head)
        ados.decode_raw(track)
        return ados


class AmigaDOS_DD(AmigaDOS):
    nsec = 11
    clock = 14/7093790

class AmigaDOS_HD(AmigaDOS):
    nsec = 22
    clock = AmigaDOS_DD.clock / 2


class AmigaDOSTrackConfig:

    default_revs = default_revs

    def __init__(self, format_name):
        self.secs = None
        self.finalised = False

    def add_param(self, key, val):
        if key == 'secs':
            val = int(val)
            error.check(val in [11, 22], '%s out of range' % key)
            self.secs = val
        else:
            raise error.Fatal('unrecognised track option %s' % key)

    def finalise(self):
        if self.finalised:
            return
        error.check(self.secs is not None,
                    'number of sectors not specified')
        self.finalised = True

    def mk_track(self, cyl, head):
        if self.secs == 11:
            t = AmigaDOS_DD(cyl, head)
        else:
            t = AmigaDOS_HD(cyl, head)
        return t


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


# Local variables:
# python-indent: 4
# End:
