# greaseweazle/flux.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

class Flux:

    def __init__(self, index_list, flux_list, sample_freq):
        self.index_list = index_list
        self.list = flux_list
        self.sample_freq = sample_freq


    def __str__(self):
        s = "Sample Frequency: %f MHz\n" % (self.sample_freq/1000000)
        s += "Total Flux: %u\n" % len(self.list)
        rev = 0
        for t in self.index_list:
            s += "Revolution %u: %.2fms\n" % (rev, t*1000/self.sample_freq)
            rev += 1
        return s[:-1]


    @classmethod
    def from_bitarray(cls, bitarray, bitrate, timing=None):
        if not timing:
            timing = [1000] * len(bitarray)
        timing_i = iter(timing)
        flux_list = []
        count = 0
        for bit in bitarray:
            count += next(timing_i)
            if bit:
                flux_list.append(count)
                count = 0
        flux_list[0] += count
        return Flux([sum(flux_list)], flux_list, bitrate * 1000)

 
# Local variables:
# python-indent: 4
# End:
