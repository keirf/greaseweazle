# greaseweazle/codec/bitcell.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from typing import List, Optional, Tuple

import struct
from bitarray import bitarray

from greaseweazle import error
from greaseweazle import optimised
from greaseweazle.codec import codec
from greaseweazle.track import MasterTrack, PLL, PLLTrack
from greaseweazle.flux import Flux, HasFlux

default_revs = 1

class BitcellTrack(codec.Codec):

    nsec = 0
    
    def __init__(self, cyl: int, head: int, config):
        self.cyl, self.head = cyl, head
        self.config = config
        self.clock = config.clock
        self.raw: Optional[PLLTrack] = None

    @property
    def time_per_rev(self) -> float:
        if self.raw is not None:
            return self.raw.time_per_rev
        if self.config.time_per_rev is not None:
            return self.config.time_per_rev
        return 0.2
        
    def summary_string(self) -> str:
        if self.raw is None:
            s = "Raw Bitcell (empty)"
        else:
            bits, _ = self.raw.get_revolution(0)
            s = ("Raw Bitcell (%d bits, %.2fms)"
                 % (len(bits), self.raw.time_per_rev*1000))
        return s

    def has_sec(self, sec_id: int) -> bool:
        return False

    def nr_missing(self) -> int:
        return 0

    def get_img_track(self) -> bytearray:
        return bytearray()

    def set_img_track(self, tdat: bytes) -> int:
        return 0

    def decode_flux(self, track: HasFlux, pll: Optional[PLL]=None) -> None:
        flux = track.flux()
        flux.cue_at_index()
        time_per_rev = self.config.time_per_rev
        if time_per_rev is None:
            time_per_rev = flux.time_per_rev
        self.raw = PLLTrack(time_per_rev = time_per_rev,
                            clock = self.clock, data = flux, pll = pll)

    def master_track(self) -> MasterTrack:
        if self.raw is None:
            nbytes = int(self.time_per_rev / self.clock) // 8
            track = MasterTrack(bits = bytes(nbytes),
                                time_per_rev = self.time_per_rev,
                                weak = [(0,nbytes*8)])
            track.force_random_weak = True
            return track
        bits, _ = self.raw.get_revolution(0)
        track = MasterTrack(bits = bits, time_per_rev = self.time_per_rev)
        return track


class BitcellTrackDef(codec.TrackDef):

    default_revs = default_revs

    def __init__(self, format_name: str):
        self.clock: Optional[float] = None
        self.time_per_rev: Optional[float] = None
        self.finalised = False

    def add_param(self, key: str, val) -> None:
        if key == 'secs':
            val = int(val)
            self.secs = val
        elif key == 'clock':
            val = float(val)
            self.clock = val * 1e-6
        elif key == 'time_per_rev':
            val = float(val)
            self.time_per_rev = val
        else:
            raise error.Fatal('unrecognised track option %s' % key)

    def finalise(self) -> None:
        if self.finalised:
            return
        error.check(self.clock is not None,
                    'clock period not specified')
        self.finalised = True

    def mk_track(self, cyl: int, head: int) -> BitcellTrack:
        return BitcellTrack(cyl, head, self)


# Local variables:
# python-indent: 4
# End:
