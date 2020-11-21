# greaseweazle/flux.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from greaseweazle import error

class Flux:

    def __init__(self, index_list, flux_list, sample_freq):
        self.index_list = index_list
        self.list = flux_list
        self.sample_freq = sample_freq
        self.splice = 0

    def __str__(self):
        s = "\nFlux: %.2f MHz" % (self.sample_freq*1e-6)
        s += ("\n Total: %u samples, %.2fms\n"
              % (len(self.list), sum(self.list)*1000/self.sample_freq))
        rev = 0
        for t in self.index_list:
            s += " Revolution %u: %.2fms\n" % (rev, t*1000/self.sample_freq)
            rev += 1
        return s[:-1]

    def flux_for_writeout(self):
        error.check(self.splice == 0,
                    "Cannot write non-index-aligned raw flux")
        # Copy the first revolution only to a fresh flux list.
        flux_list = []
        to_index = remain = self.index_list[0]
        for f in self.list:
            if f > remain:
                break
            flux_list.append(f)
            remain -= f
        # Extend with "safe" 4us sample values, to avoid unformatted area
        # at end of track if drive motor is a little slow.
        four_us = max(self.sample_freq * 4e-6, 1)
        if remain > four_us:
            flux_list.append(remain)
        for i in range(round(to_index/(10*four_us))):
            flux_list.append(four_us)
        return WriteoutFlux(to_index, flux_list, self.sample_freq,
                            terminate_at_index = True)

    def flux(self):
        return self

    def scale(self, factor):
        """Scale up all flux and index timings by specified factor."""
        self.sample_freq /= factor

    @property
    def mean_index_time(self):
        """Mean time between index pulses, in seconds (float)"""
        return sum(self.index_list) / (len(self.index_list) * self.sample_freq)


class WriteoutFlux(Flux):

    def __init__(self, ticks_to_index, flux_list, sample_freq,
                 terminate_at_index):
        super().__init__([ticks_to_index], flux_list, sample_freq)
        self.terminate_at_index = terminate_at_index

    def __str__(self):
        s = ("\nWriteoutFlux: %.2f MHz, %.2fms to index, %s\n"
             " Total: %u samples, %.2fms"
             % (self.sample_freq*1e-6,
                self.index_list[0]*1000/self.sample_freq,
                ("Write all", "Terminate at index")[self.terminate_at_index],
                len(self.list), sum(self.list)*1000/self.sample_freq))
        return s

    def flux_for_writeout(self):
        return self
 
# Local variables:
# python-indent: 4
# End:
