# greaseweazle/codec/hp/micropolis.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.

from typing import List, Optional

import struct
from bitarray import bitarray
import crcmod.predefined
import itertools as it
from enum import Enum

from greaseweazle import error
from greaseweazle.codec import codec
from greaseweazle.codec.ibm.ibm import decode, encode, fm_encode, mfm_encode
from greaseweazle.track import MasterTrack, PLL, PLLTrack
from greaseweazle.flux import HasFlux

default_revs = 1

bad_sector = b'-=[BAD SECTOR]=-'

mfm_sync = bitarray(endian='big')
mfm_sync.frombytes(mfm_encode(encode(b'\x00\x00\x00\xff')))

# Sector format is:
#  40: 00 preamble
#   1: FF sync
#   2: track, sector
#  10: padding/vendor
# 256: payload
#   1: checksum
#   5: ecc [optional]
#  NN: 00 postamble

def micropolis_csum(dat):
    y = 0
    for x in dat:
        if y > 255:
            y -= 255
        y += x
    # Ignore carry on last addition
    return y & 255

class Micropolis(codec.Codec):

    time_per_rev = 0.2

    verify_revs: float = default_revs

    def __init__(self, cyl: int, head: int, config):
        self.clock = 2e-6
        self.presync_bytes = 40
        self.cyl, self.head = cyl, head
        self.config = config
        self.sector: List[Optional[bytes]]
        self.sector = [None] * self.nsec

    @property
    def nsec(self) -> int:
        return self.config.secs

    @property
    def img_bps(self) -> int:
        return self.config.img_bps

    def summary_string(self) -> str:
        nsec, nbad = self.nsec, self.nr_missing()
        s = "Micropolis (%d/%d sectors)" % (nsec - nbad, nsec)
        return s

    def bad_sector(self) -> bytes:
        if self.img_bps == 256:
            return bad_sector * 16
        return b'\xff' + bytes(12) + bad_sector*16 + bytes(6)

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
            tdat += sec if sec is not None else self.bad_sector()
        return tdat

    def set_img_track(self, tdat: bytes) -> int:
        totsize = self.nsec * self.img_bps
        if len(tdat) < totsize:
            tdat += bytes(totsize - len(tdat))
        for sec in range(self.nsec):
            self.sector[sec] = tdat[sec*self.img_bps:(sec+1)*self.img_bps]
        return totsize

    def decode_flux(self, track: HasFlux, pll: Optional[PLL]=None) -> None:
        flux = track.flux()
        if flux.time_per_rev < self.time_per_rev / 2:
            flux.identify_hard_sectors()
        flux.cue_at_index()
        raw = PLLTrack(time_per_rev = self.time_per_rev,
                       clock = self.clock, data = flux, pll = pll)

        for rev in range(len(raw.revolutions)):

            if self.nr_missing() == 0:
                break

            bits, _ = raw.get_revolution(rev)

            hardsector_bits = raw.revolutions[rev].hardsector_bits
            if hardsector_bits is not None:
                hardsector_bits = list(it.accumulate(hardsector_bits))
            else:
                hardsector_bits = [len(bits)*(i+1)//self.nsec
                                   for i in range(self.nsec)]
            error.check(len(hardsector_bits) == self.nsec,
                        f'North Star: Unexpected number of sectors: '
                        f'{len(hardsector_bits)}')
            hardsector_bits = [0] + hardsector_bits

            for hsec_id in range(self.nsec):

                s, e = hardsector_bits[hsec_id], hardsector_bits[hsec_id+1]
                # Skip first 50 cells (~100us) to avoid false sync
                # Reference: Vector Micropolis Disk Controller Board Technical
                # Information Manual, pp. 1-16.
                s += 50
                offs = bits[s:e].search(mfm_sync)
                for off in offs:
                    off += 3*16
                    dat = decode(bits[s+off:s+off+275*16].tobytes())
                    if len(dat) != 275:
                        continue
                    cyl, sec_id = dat[1], dat[2]
                    if cyl != self.cyl or sec_id > self.nsec:
                        print('T%d.%d: Ignoring unexpected sector C:%d R:%d'
                              % (self.cyl, self.head, cyl, sec_id))
                        continue
                    if self.has_sec(sec_id):
                        continue
                    if micropolis_csum(dat[1:-6]) == dat[-6]:
                        if hsec_id != sec_id:
                            print(f'T{self.cyl, self.head}: Weird skew: '
                                  f'hsec {hsec_id} contains sector {sec_id}')
                        if self.img_bps == 256:
                            self.add(sec_id, dat[13:13+256])
                        else:
                            self.add(sec_id, dat)
                        break # We are done on this hard sector


    def master_track(self) -> MasterTrack:

        t = bytes()
        slen = int((self.time_per_rev / self.clock / self.nsec / 16))

        for sec_id in range(self.nsec):
            s = encode(bytes(self.presync_bytes))
            sector = self.sector[sec_id]
            sector = self.bad_sector() if sector is None else sector
            if len(sector) == 256:
                dat = b'\xff' + bytes([self.cyl, sec_id]) + bytes(10)
                dat += sector
                dat += bytes([micropolis_csum(dat[1:])])
            else:
                if sector[0] != 0xff:
                    print("T%u.%u: 275-byte sector doesn't start with FF sync"
                          % (self.cyl, self.head))
                dat = sector
            s += encode(dat)
            s += encode(bytes(slen - len(s)//2))
            t += s

        t = mfm_encode(t)

        track = MasterTrack(bits = t, time_per_rev = self.time_per_rev,
                            hardsector_bits = [slen*16] * self.nsec)
        track.verify = self
        return track


    def verify_track(self, flux):
        readback_track = self.__class__(self.cyl, self.head, self.config)
        readback_track.decode_flux(flux)
        return (readback_track.nr_missing() == 0
                and self.sector == readback_track.sector)


class MicropolisDef(codec.TrackDef):

    default_revs = default_revs

    def __init__(self, format_name: str):
        self.secs: Optional[int] = None
        self.img_bps: Optional[int] = None
        self.finalised = False

    def add_param(self, key: str, val) -> None:
        if key == 'secs':
            val = int(val)
            self.secs = val
        elif key == 'img_bps':
            val = int(val)
            self.img_bps = val
            error.check(val in [256, 275], f'bad img_bps {val}')
        else:
            raise error.Fatal('unrecognised track option %s' % key)

    def finalise(self) -> None:
        if self.finalised:
            return
        error.check(self.secs is not None,
                    'number of sectors not specified')
        error.check(self.img_bps is not None,
                    'img_bps not specified')
        self.finalised = True

    def mk_track(self, cyl: int, head: int) -> Micropolis:
        return Micropolis(cyl, head, self)


# Local variables:
# python-indent: 4
# End:
