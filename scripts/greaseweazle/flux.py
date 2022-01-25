# greaseweazle/flux.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from greaseweazle import error


class Flux:

    def __init__(self, index_list, flux_list, sample_freq, index_cued=True):
        self.index_list = index_list
        self.list = flux_list
        self.sample_freq = sample_freq
        self.splice = 0
        self.index_cued = index_cued


    def __str__(self):
        s = "\nFlux: %.2f MHz" % (self.sample_freq*1e-6)
        s += ("\n Total: %u samples, %.2fms\n"
              % (len(self.list), sum(self.list)*1000/self.sample_freq))
        rev = 0
        for t in self.index_list:
            s += " Revolution %u: %.2fms\n" % (rev, t*1000/self.sample_freq)
            rev += 1
        return s[:-1]


    def summary_string(self):
        return ("Raw Flux (%u flux in %.2fms)"
                % (len(self.list), sum(self.list)*1000/self.sample_freq))


    def append(self, flux):
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


    def cue_at_index(self):

        if self.index_cued:
            return

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


    def flux_for_writeout(self):

        error.check(self.index_cued,
                    "Cannot write non-index-cued raw flux")
        error.check(self.splice == 0 or len(self.index_list) > 1,
                    "Cannot write single-revolution unaligned raw flux")
        splice_at_index = (self.splice == 0)

        # Copy the required amount of flux to a fresh list.
        flux_list = []
        to_index = self.index_list[0]
        remain = to_index + self.splice
        for f in self.list:
            if f > remain:
                break
            flux_list.append(f)
            remain -= f

        if splice_at_index:
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
                            index_cued = True,
                            terminate_at_index = (self.splice == 0))



    def flux(self):
        return self


    def scale(self, factor):
        """Scale up all flux and index timings by specified factor."""
        self.sample_freq /= factor


    @property
    def ticks_per_rev(self):
        """Mean time between index pulses, in sample ticks"""
        index_list = self.index_list
        if not self.index_cued:
            index_list = index_list[1:]
        return sum(index_list) / len(index_list)


    @property
    def time_per_rev(self):
        """Mean time between index pulses, in seconds (float)"""
        return self.ticks_per_rev / self.sample_freq


class WriteoutFlux(Flux):

    def __init__(self, ticks_to_index, flux_list, sample_freq,
                 index_cued, terminate_at_index):
        super().__init__([ticks_to_index], flux_list, sample_freq)
        self.index_cued = index_cued
        self.terminate_at_index = terminate_at_index


    def __str__(self):
        s = ("\nWriteoutFlux: %.2f MHz, %.2fms to index, %s\n"
             " Total: %u samples, %.2fms"
             % (self.sample_freq*1e-6,
                self.index_list[0]*1000/self.sample_freq,
                ("Write all", "Terminate at index")[self.terminate_at_index],
                len(self.list), sum(self.list)*1000/self.sample_freq))
        return s


    def summary_string(self):
        s = ("Flux: %.1fms period, %.1f ms total, %s"
             % (self.index_list[0]*1000/self.sample_freq,
                sum(self.list)*1000/self.sample_freq,
                ("Write all", "Terminate at index")[self.terminate_at_index]))
        return s


    def flux_for_writeout(self):
        return self
 

    @property
    def ticks_per_rev(self):
        """Mean time between index pulses, in sample ticks"""
        return sum(self.index_list) / len(self.index_list)


# Local variables:
# python-indent: 4
# End:
