# greaseweazle/bitcell.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import binascii
import itertools as it
from bitarray import bitarray

class Bitcell:

    def __init__(self, clock = 2e-6, flux = None):
        self.clock = clock
        self.clock_max_adj = 0.10
        self.pll_period_adj = 0.05
        self.pll_phase_adj = 0.60
        self.bitarray = bitarray(endian='big')
        self.timearray = []
        self.revolutions = []
        if flux is not None:
            self.from_flux(flux)

        
    def __str__(self):
        s = ""
        for rev in range(len(self.revolutions)):
            b, _ = self.get_revolution(rev)
            s += "Revolution %u: " % rev
            s += str(binascii.hexlify(b.tobytes())) + "\n"
        return s[:-1]

    
    def get_revolution(self, nr):
        start = sum(self.revolutions[:nr])
        end = start + self.revolutions[nr]
        return self.bitarray[start:end], self.timearray[start:end]

    
    def from_flux(self, flux):

        freq = flux.sample_freq

        clock = self.clock
        clock_min = self.clock * (1 - self.clock_max_adj)
        clock_max = self.clock * (1 + self.clock_max_adj)
        ticks = 0.0

        index_iter = iter(map(lambda x: x/freq, flux.index_list))

        bits, times = bitarray(endian='big'), []
        to_index = next(index_iter)

        # Make sure there's enough time in the flux list to cover all
        # revolutions by appending a "large enough" final flux value.
        for x in it.chain(flux.list, [sum(flux.index_list)]):

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
                    self.bitarray += bits
                    self.timearray += times
                    self.revolutions.append(len(times))
                    assert len(times) == len(bits)
                    try:
                        to_index += next(index_iter)
                    except StopIteration:
                        return
                    bits, times = bitarray(endian='big'), []

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

        # We can't get here: We should run out of indexes before we run
        # out of flux.
        assert False

# Local variables:
# python-indent: 4
# End:
