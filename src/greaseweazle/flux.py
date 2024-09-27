# greaseweazle/flux.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from __future__ import annotations
from typing import List, Optional, Protocol

from greaseweazle import error

class HasFlux(Protocol):
    def summary_string(self) -> str:
        ...
    def flux(self) -> Flux:
        ...
    def flux_for_writeout(self, cue_at_index) -> WriteoutFlux:
        ...

class Flux:

    _ticks_per_rev: float
    
    def __init__(self,
                 index_list: List[float],
                 flux_list: List[float],
                 sample_freq: float,
                 index_cued = True) -> None:
        self.index_list = index_list
        self.sector_list: Optional[List[List[float]]] = None
        self.list = flux_list
        self.sample_freq = sample_freq
        self.splice: Optional[float] = None
        self.index_cued = index_cued


    def __str__(self) -> str:
        s = "\nFlux: %.2f MHz" % (self.sample_freq*1e-6)
        if self.index_cued: s += ", Index-Cued"
        s += ("\n Total: %u samples, %.2fms\n"
              % (len(self.list), sum(self.list)*1000/self.sample_freq))
        for rev, t in enumerate(self.index_list):
            s += " Revolution %u: %.2fms\n" % (rev, t*1000/self.sample_freq)
            if self.sector_list:
                for sec, t in enumerate(self.sector_list[rev]):
                    s += ("    Sector %u: %.2fms\n"
                          % (sec, t*1000/self.sample_freq))
        return s[:-1]


    def summary_string(self) -> str:
        return ("Raw Flux (%u flux in %.2fms)"
                % (len(self.list), sum(self.list)*1000/self.sample_freq))


    def identify_hard_sectors(self) -> None:
        if self.sector_list is not None:
            return
        error.check(len(self.index_list) > 3,
                    "Not enough index marks for a hard-sectored track")
        self.cue_at_index()
        x = [self.index_list[0], self.index_list[2]]
        x.sort()
        thresh = x[1] * 3 / 4
        ticks_to_index: float = 0
        short_ticks: float = 0
        sectors: List[float] = []
        index_list = self.index_list
        self.index_list = []
        self.sector_list = []
        short_count = 0
        for t in index_list:
            is_short = (t < thresh)
            if is_short:
                short_ticks += t
                short_count += 1
            # Latch an index when we see two short pulses, or a long pulse
            # following at least one short pulse.
            if short_count != 0 and (short_count > 1 or not is_short):
                ticks_to_index += short_ticks
                sectors.append(short_ticks)
                self.index_list.append(ticks_to_index)
                self.sector_list.append(sectors)
                sectors = []
                short_ticks = ticks_to_index = short_count = 0
            if not is_short:
                ticks_to_index += t
                sectors.append(t)
        error.check(len(self.index_list) > 0,
                    "No hard-sector index mark found")
        self.index_cued = (
            (len(self.index_list) >= 2) and
            (len(self.sector_list[0]) == len(self.sector_list[1])))


    def append(self, flux: Flux) -> None:
        # Scale the new flux if required, to match existing sample frequency.
        # This will result in floating-point flux values.
        if self.sample_freq == flux.sample_freq:
            f_list, i_list = flux.list, flux.index_list
        else:
            factor = self.sample_freq / flux.sample_freq
            f_list = [x*factor for x in flux.list]
            i_list = [x*factor for x in flux.index_list]
        # Any trailing flux is incorporated into the first revolution of
        # the appended flux.
        rev0 = i_list[0] + sum(self.list) - sum(self.index_list)
        self.index_list += [rev0] + i_list[1:]
        self.list += f_list
        # TODO: Work with hard-sectored disks
        self.sector_list = None


    def cue_at_index(self) -> None:

        if self.index_cued:
            return

        error.check(len(self.index_list) >= 2,
                    '''\
                    Not enough revolutions of flux data to cue at index.
                    Try dumping more revolutions (larger --revs value).''')

        # Clip the initial partial revolution.
        to_index = self.index_list[0]
        for i in range(len(self.list)):
            to_index -= self.list[i]
            if to_index < 0:
                break
        if to_index < 0:
            self.list = [-to_index] + self.list[i+1:]
        else: # we ran out of flux
            self.list = []
        self.index_list = self.index_list[1:]
        self.index_cued = True
        if self.sector_list:
            self.sector_list = self.sector_list[1:]


    def reverse(self) -> None:

        assert self.sector_list is None

        was_index_cued = self.index_cued
        flux_sum = sum(self.list)

        self.index_cued = False
        self.list.reverse()
        self.index_list.reverse()

        to_index = flux_sum - sum(self.index_list)
        if to_index <= 0:
            if to_index < 0:
                self.list.insert(0, -to_index)
                flux_sum += -to_index
            self.index_list = self.index_list[1:]
            self.index_cued = True
        else:
            self.index_list = [to_index] + self.index_list[:-1]

        if was_index_cued:
            self.index_list.append(flux_sum - sum(self.index_list))


    def set_nr_revs(self, revs:int) -> None:

        self.cue_at_index()
        error.check(self.index_list,
                    'Need at least one revolution to adjust # revolutions')

        if len(self.index_list) > revs:
            self.index_list = self.index_list[:revs]
            if self.sector_list:
                self.sector_list = self.sector_list[:revs]
            to_index = sum(self.index_list)
            for i in range(len(self.list)):
                to_index -= self.list[i]
                if to_index < 0:
                    self.list = self.list[:i]
                    break

        while len(self.index_list) < revs:
            nr = min(revs - len(self.index_list), len(self.index_list))
            to_index = sum(self.index_list[:nr])
            l = self.list
            for i in range(len(l)):
                to_index -= l[i]
                if to_index < 0:
                    to_index += l[i]
                    l = l[:i]
                    break
            if self.list:
                self.list = l + [to_index + self.list[0]] + self.list[1:]
            self.index_list = self.index_list[:nr] + self.index_list
            if self.sector_list:
                self.sector_list = self.sector_list[:nr] + self.sector_list

    def flux_for_writeout(self, cue_at_index) -> WriteoutFlux:

        # Splice at index unless we know better.
        splice = 0 if self.splice is None else self.splice

        error.check(self.index_cued,
                    "Cannot write non-index-cued raw flux")
        error.check(splice == 0 or len(self.index_list) > 1,
                    "Cannot write single-revolution unaligned raw flux")
        splice_at_index = (splice == 0)

        # Copy the required amount of flux to a fresh list.
        flux_list = []
        to_index = self.index_list[0]
        remain = to_index + splice
        for f in self.list:
            if f > remain:
                break
            flux_list.append(f)
            remain -= f

        if not cue_at_index:
            # We will write more than one revolution and terminate the
            # second revolution at the splice. Extend the start of the write
            # with "safe" 4us sample values, in case the drive motor is a
            # little fast.
            if remain > 0:
                flux_list.append(remain)
            prepend = max(round(to_index/10 - splice), 0)
            if prepend != 0:
                four_us = max(self.sample_freq * 4e-6, 1)
                flux_list = [four_us]*round(prepend/four_us) + flux_list
            splice_at_index = False
        elif splice_at_index:
            # Extend with "safe" 4us sample values, to avoid unformatted area
            # at end of track if drive motor is a little slow.
            four_us = max(self.sample_freq * 4e-6, 1)
            if remain > four_us:
                flux_list.append(remain)
            for i in range(round(to_index/(10*four_us))):
                flux_list.append(four_us)
        elif remain > 0:
            # End the write exactly where specified.
            flux_list.append(remain)

        return WriteoutFlux(to_index, flux_list, self.sample_freq,
                            index_cued = cue_at_index,
                            terminate_at_index = splice_at_index)



    def flux(self) -> Flux:
        return self


    def scale(self, factor) -> None:
        """Scale up all flux and index timings by specified factor."""
        self.sample_freq /= factor


    @property
    def ticks_per_rev(self) -> float:
        """Mean time between index pulses, in sample ticks"""
        try:
            index_list = self.index_list
            if not self.index_cued:
                index_list = index_list[1:]
            ticks_per_rev = sum(index_list) / len(index_list)
        except:
            ticks_per_rev = self._ticks_per_rev
        return ticks_per_rev


    @property
    def time_per_rev(self) -> float:
        """Mean time between index pulses, in seconds (float)"""
        return self.ticks_per_rev / self.sample_freq


class WriteoutFlux:

    def __init__(
            self,
            ticks_to_index: float,
            flux_list: List[float],
            sample_freq: float,
            index_cued: bool,
            terminate_at_index: bool
    ) -> None:
        self.ticks_to_index = ticks_to_index
        self.list = flux_list
        self.sample_freq = sample_freq
        self.index_cued = index_cued
        self.terminate_at_index = terminate_at_index


    def __str__(self) -> str:
        s = ("\nWriteoutFlux: %.2f MHz, %.2fms to index, %s\n"
             " Total: %u samples, %.2fms"
             % (self.sample_freq*1e-6,
                self.ticks_to_index*1000/self.sample_freq,
                ("Write all", "Terminate at index")[self.terminate_at_index],
                len(self.list), sum(self.list)*1000/self.sample_freq))
        return s


    def summary_string(self) -> str:
        s = ("Flux: %.1fms period, %.1f ms total, %s"
             % (self.ticks_to_index*1000/self.sample_freq,
                sum(self.list)*1000/self.sample_freq,
                ("Write all", "Terminate at index")[self.terminate_at_index]))
        return s


# Local variables:
# python-indent: 4
# End:
