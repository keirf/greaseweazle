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
        self.terminate_at_index = True


    def __str__(self):
        s = "Sample Frequency: %f MHz\n" % (self.sample_freq/1000000)
        s += "Total Flux: %u\n" % len(self.list)
        rev = 0
        for t in self.index_list:
            s += "Revolution %u: %.2fms\n" % (rev, t*1000/self.sample_freq)
            rev += 1
        return s[:-1]


    def flux_for_writeout(self):
        return self

 
# Local variables:
# python-indent: 4
# End:
