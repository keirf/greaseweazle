# greaseweazle/image/a2r.py
#
# Applesauce 3.x image format.
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from typing import Dict, Tuple, Optional, List

import struct

from greaseweazle import error
from greaseweazle.flux import Flux
from .image import Image

class A2RCapType:
    timing  = 1
    bits    = 2
    xtiming = 3


class A2RTrack:

    def __init__(self, cyl: int, head: int, ps_per_tick: int):
        self.cyl, self.head = cyl, head
        self.sample_freq = 1e12 / ps_per_tick
        self.caps: List[bytes] = list()


    def add_cap(self, cap) -> None:
        self.caps.append(cap)


    def best_cap(self) -> bytes:
        # Look for a trace with two index pulses. This is correct for the
        # claimed 2.25 revolutions of an index-cued xtiming capture.
        for dat in self.caps:
            if dat[4] == 2:
                return dat
        return self.caps[-1]


    def flux(self) -> Flux:
        dat = self.best_cap()

        # Decode the index list.
        nidx = dat[4]
        i = 5+nidx*4
        index_list = list(struct.unpack(f'<{nidx}I', dat[5:i]))
        for i in range(len(index_list)-1, 0, -1):
            index_list[i] -= index_list[i-1]
        ncap, = struct.unpack('<I', dat[i:i+4])
        i += 4

        # Decode the flux list.
        flux_list: List[float] = []
        acc = 0
        for f in dat[i:i+ncap]:
            acc += f
            if f != 255:
                flux_list.append(acc)
                acc = 0
        if acc != 0:
            flux_list.append(acc)

        flux = Flux(index_list, flux_list, self.sample_freq)
        return flux


class A2R(Image):

    read_only = True


    def __init__(self, name: str, _fmt) -> None:
        self.to_track: Dict[Tuple[int,int], A2RTrack] = dict()
        self.filename = name


    def process_rwcp(self, dat: bytes) -> None:

        ps_per_tick, = struct.unpack('<I', dat[1:5])
        i = 16

        while dat[i] == ord('C'):

            start = i

            # Basic decoding, sufficient to skip unwanted capture types.
            cap, loc, nidx = struct.unpack('<BHB', dat[i+1:i+5])
            cyl, head = loc>>1, loc&1
            i += 5 + nidx*4
            ncap, = struct.unpack('<I', dat[i:i+4])
            i += 4 + ncap

            # Store away (x)timing captures for future decode.
            if cap != A2RCapType.xtiming and cap != A2RCapType.timing:
                continue
            if not (cyl, head) in self.to_track:
                t = A2RTrack(cyl, head, ps_per_tick)
                self.to_track[cyl, head] = t
            else:
                t = self.to_track[cyl, head]
            t.add_cap(dat[start:i])
    

    def from_bytes(self, dat: bytes) -> None:

        error.check(dat[:8] == b'A2R3\xff\x0a\x0d\x0a',
                    'A2R: Invalid signature')
        dat = dat[8:]

        # Extract the RWCP chunk(s).
        while len(dat) > 8:
            id, sz = struct.unpack('<4sI', dat[:8])
            dat = dat[8:]
            if id == b'RWCP':
                self.process_rwcp(dat)
            dat = dat[sz:]


    def get_track(self, cyl: int, side: int) -> Optional[Flux]:
        if not (cyl, side) in self.to_track:
            return None
        track = self.to_track[cyl, side]
        return track.flux()


# Local variables:
# python-indent: 4
# End:
