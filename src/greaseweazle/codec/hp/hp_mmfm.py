# greaseweazle/codec/hp/hp_mmfm.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.

# From github:brouhaha/fluxtoimd/modulation.py:
#
# See the file COPYING for more details, or visit <http://unlicense.org>.
# An HP-proprietary M2FM floppy format, used by the HP 7902, 9885,
# and 9895 Flexible Disc Drives.
# Documentation:
#   9885 Flexible Disk Drive Service Manual
#      Hewlett-Packard, September 1976, part number 09885-90030
#   7902A Disc Drive Preliminary Service Manual
#      Hwelett Packard, May 1979, part number 07902-90060
#   7902A & C/9895K Flexible Disc Drive Service Documentation
#      Hewlett-Packard, January 1981, part number 07902-90030
#   9895A Flexible Disc Memory Service Manual,
#      Hewlett-Packard, February 1981, part number 09895-90030
# 9885: single-sided, 67 track, M2FM format only
# 7902: double-sided, 77 track, M2FM or IBM 3740 FM formats
# 9895: double-sided, 77 track, M2FM or IBM 3740 FM formats

from typing import List, Optional

import struct
from bitarray import bitarray
import crcmod.predefined

from greaseweazle import error
from greaseweazle.codec import codec
from greaseweazle.codec.ibm.ibm import decode, encode, sec_map
from greaseweazle.track import MasterTrack, PLL, PLLTrack
from greaseweazle.flux import HasFlux

default_revs = 1.1

bad_sector = b'-=[BAD SECTOR]=-' * 16

# Syncs have an extra clock bit:
# ff 0e -> 55 55 22 54 -> 55 55 2a 54
sector_sync_bytes = b'\x55\x55\x2a\x54'
# ff 0a -> 55 55 22 44 -> 55 55 2a 44
data_sync_bytes = b'\x55\x55\x2a\x44'

sector_sync = bitarray(endian='big')
sector_sync.frombytes(sector_sync_bytes)

data_sync = bitarray(endian='big')
data_sync.frombytes(data_sync_bytes)

crc16 = crcmod.predefined.Crc('crc-ccitt-false')

rev_list = bytearray()
for x in range(256):
    y = 0
    for i in range(8):
        y <<= 1
        y |= x & 1
        x >>= 1
    rev_list.append(y)

def bitrev(x):
    return rev_list[x]

# MMFM:
# Write clock bit iff
#  1. No preceding clock or data
#  2. No following data
mmfm_list = bytearray()
for x in range(512):
    for i in [7,5,3,1]:
        if x & (0xf << (i-1)) == 0:
            x |= 1<<i
    mmfm_list.append(x & 255)

def mmfm_encode(dat):
    y, out = 0, bytearray()
    for x in dat:
        if (x & 0xaa) == 0:
            x = mmfm_list[(y<<8) | x]
        out.append(x)
        y = 0 if (x & 3) == 0 else 1
    return bytes(out)

class HPMMFM(codec.Codec):

    time_per_rev = 60 / 360
    clock = 1e-6

    verify_revs = default_revs

    def __init__(self, cyl: int, head: int, config):
        self.cyl, self.head = cyl, head
        self.config = config
        self.sector: List[Optional[bytes]]
        self.sector = [None] * self.nsec

    @property
    def nsec(self) -> int:
        return self.config.secs

    def summary_string(self) -> str:
        nsec, nbad = self.nsec, self.nr_missing()
        s = "HP MMFM (%d/%d sectors)" % (nsec - nbad, nsec)
        return s

    # private
    def add(self, sec_id, data) -> None:
        assert not self.has_sec(sec_id)
        self.sector[sec_id] = data

    def has_sec(self, sec_id: int) -> bool:
        return self.sector[sec_id] is not None

    def nr_missing(self) -> int:
        return len([sec for sec in self.sector if sec is None])

    def get_img_track(self) -> bytearray:
        tdat = bytearray()
        for sec in self.sector:
            tdat += sec if sec is not None else bad_sector
        return tdat

    def set_img_track(self, tdat: bytes) -> int:
        totsize = self.nsec * 256
        if len(tdat) < totsize:
            tdat += bytes(totsize - len(tdat))
        for sec in range(self.nsec):
            self.sector[sec] = tdat[sec*256:(sec+1)*256]
        return totsize

    def decode_flux(self, track: HasFlux, pll: Optional[PLL]=None) -> None:
        raw = PLLTrack(time_per_rev = self.time_per_rev,
                       clock = self.clock, data = track, pll = pll)
        bits, _ = raw.get_all_data()

        for offs in bits.search(sector_sync):

            if self.nr_missing() == 0:
                break

            offs += 2*16
            idam = decode(bits[offs:offs+4*16].tobytes())
            if len(idam) != 4:
                continue
            if crc16.new(idam).crcValue != 0:
                continue
            cyl = bitrev(idam[0])
            sec_id = bitrev(idam[1])
            head = (sec_id & 128) == 128
            sec_id &= 127
            if cyl != self.cyl or head != self.head or sec_id > self.nsec:
                print('T%d.%d: Ignoring unexpected sector C:%d H:%d R:%d'
                      % (self.cyl, self.head, cyl, head, sec_id))
                continue
            if self.has_sec(sec_id):
                continue

            # Find data
            offs += 8*16
            dat_offs = list(bits[offs:offs+50*16].search(data_sync))
            if len(dat_offs) != 1:
                continue
            offs += dat_offs[0] + 2*16

            sec = decode(bits[offs:offs+258*16].tobytes())
            if len(sec) != 258:
                continue
            if crc16.new(sec).crcValue != 0:
                continue

            # bit swap, and byte swap
            sec = bytes(map(lambda x: bitrev(x), sec[:256]))
            sec = struct.pack('<128H', *struct.unpack('>128H', sec))

            self.add(sec_id, sec)


    def master_track(self) -> MasterTrack:

        # Post-index track gap.
        t = encode(bytes(100))

        for sec_id in sec_map(self.nsec, self.config.interleave,
                              self.config.cskew, self.config.hskew,
                              self.cyl, self.head):
            sector = self.sector[sec_id]
            data = bad_sector if sector is None else sector
            # Header
            t += encode(bytes([0xff]*3)) + sector_sync_bytes
            idam = bytes(map(lambda x: bitrev(x),
                             [self.cyl, sec_id | (self.head << 7)]))
            idam += struct.pack('>H', crc16.new(idam).crcValue)
            t += encode(idam)
            t += encode(bytes(1 + 16 + 4))
            # Data
            t += encode(bytes([0xff]*3)) + data_sync_bytes
            data = struct.pack('<128H', *struct.unpack('>128H', data))
            data = bytes(map(lambda x: bitrev(x), data))
            data += struct.pack('>H', crc16.new(data).crcValue)
            t += encode(data)
            t += encode(bytes(1 + 34 + 4))

        # Add the pre-index gap.
        tlen = int((self.time_per_rev / self.clock)) & ~31
        t += encode(bytes((tlen//8-len(t))//2))

        t = mmfm_encode(t)

        track = MasterTrack(bits = t, time_per_rev = self.time_per_rev)
        track.verify = self
        return track


    def verify_track(self, flux):
        readback_track = self.__class__(self.cyl, self.head, self.config)
        readback_track.decode_flux(flux)
        return (readback_track.nr_missing() == 0
                and self.sector == readback_track.sector)


class HPMMFMDef(codec.TrackDef):

    default_revs = default_revs

    def __init__(self, format_name: str):
        self.interleave = 1
        self.cskew, self.hskew = 0, 0
        self.secs: Optional[int] = None
        self.finalised = False

    def add_param(self, key: str, val) -> None:
        if key == 'secs':
            val = int(val)
            self.secs = val
        elif key in ['interleave', 'cskew', 'hskew']:
            n = int(val)
            error.check(0 <= n <= 255, '%s out of range' % key)
            setattr(self, key, n)
        else:
            raise error.Fatal('unrecognised track option %s' % key)

    def finalise(self) -> None:
        if self.finalised:
            return
        error.check(self.secs is not None,
                    'number of sectors not specified')
        self.finalised = True

    def mk_track(self, cyl: int, head: int) -> HPMMFM:
        return HPMMFM(cyl, head, self)


# Local variables:
# python-indent: 4
# End:
