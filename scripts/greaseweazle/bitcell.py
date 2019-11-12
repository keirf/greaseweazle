# greaseweazle/bitcell.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import binascii
from bitarray import bitarray

class Bitcell:

    def __init__(self):
        self.clock = 2 / 1000000
        self.clock_max_adj = 0.10
        self.pll_period_adj = 0.05
        self.pll_phase_adj = 0.60

    def __str__(self):
        s = ""
        rev = 0
        for b, _ in self.revolution_list:
            s += "Revolution %u: " % rev
            s += str(binascii.hexlify(b.tobytes())) + "\n"
            rev += 1
        return s[:-1]

    def read_flux(self, flux):

        index_list, freq = flux.index_list, flux.sample_freq

        clock = self.clock
        clock_min = self.clock * (1 - self.clock_max_adj)
        clock_max = self.clock * (1 + self.clock_max_adj)
        ticks = 0.0

        # Per-revolution list of bitcells and bitcell times.
        self.revolution_list = []

        # Initialise bitcell lists for the first revolution.
        bits, times = bitarray(), []
        to_index = index_list[0] / freq
        index_list = index_list[1:]

        for x in flux.list:

            # Gather enough ticks to generate at least one bitcell.
            ticks += x / freq
            if ticks < clock/2:
                continue

            # Clock out zero or more 0s, followed by a 1.
            zeros = 0
            while True:

                # Check if we cross the index mark.
                to_index -= clock
                if to_index < 0:
                    self.revolution_list.append((bits, times))
                    if not index_list:
                        return
                    bits, times = bitarray(), []
                    to_index = index_list[0] / freq
                    index_list = index_list[1:]

                ticks -= clock
                times.append(clock)
                if ticks >= clock/2:
                    zeros += 1
                    bits.append(False)
                else:
                    bits.append(True)
                    break

            # PLL: Adjust clock frequency according to phase mismatch.
            if zeros <= 3:
                # In sync: adjust clock by a fraction of the phase mismatch.
                clock += ticks * self.pll_period_adj
            else:
                # Out of sync: adjust clock towards centre.
                clock += (self.clock - clock) * self.pll_period_adj
            # Clamp the clock's adjustment range.
            clock = min(max(clock, clock_min), clock_max)
            # PLL: Adjust clock phase according to mismatch.
            new_ticks = ticks * (1 - self.pll_phase_adj)
            times[-1] += ticks - new_ticks
            ticks = new_ticks

        self.revolution_list.append((bits, times))

# Local variables:
# python-indent: 4
# End:
