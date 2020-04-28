# greaseweazle/track.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import binascii
from bitarray import bitarray
from greaseweazle.flux import Flux

# A pristine representation of a track, from a codec and/or a perfect image.
class MasterTrack:

    @property
    def bitrate(self):
        return len(self.bitarray) / self.time_per_rev

    # bits: Track bitcell data (bitarray)
    # time_per_rev: Time per revolution, in seconds (float)
    # bit_ticks: Per-bitcell time values, in unitless 'ticks'
    # splice: Location of the track splice, in bitcells, after the index.
    def __init__(self, bits, time_per_rev):
        self.bits = bits
        self.time_per_rev = time_per_rev
        self.bit_ticks = None
        self.splice = 0

    def __str__(self):
        s = "\nMaster Track:\n"
        s += (" %d bits, %.1f kbit/s"
              % (len(self.bits), self.bitrate))
        if self.bit_ticks:
            s += " (variable)"
        s += ("\n Total Time = %.1f ms (%.1f rpm)\n "
              % (self.time_per_rev * 1000, 60 / self.time_per_rev))
        #s += str(binascii.hexlify(self.bits.tobytes()))
        return s

    def flux_for_writeout(self):

        # We're going to mess with the track data, so take a copy.
        bits = self.bits.copy()
        bitlen = len(bits)

        # Also copy the bit_ticks array (or create a dummy one), and remember
        # the total ticks that it contains.
        bit_ticks = self.bit_ticks.copy() if self.bit_ticks else [1] * bitlen
        ticks_to_index = sum(bit_ticks)

        splice_at_index = self.splice < 4 or bitlen - self.splice < 4

        if splice_at_index:
            # Splice is at the index (or within a few bitcells of it).
            # We stretch the track with extra bytes of filler, in case the
            # drive motor spins slower than expected and we need more filler
            # to get us to the index pulse (where the write will terminate).
            # Thus if the drive spins slow, the track gets a longer footer.
            pos = bitlen-4 if self.splice < 4 else self.splice-4
            tick_pattern = bit_ticks[pos-32:pos]
            fill_pattern = bits[pos-32:pos]
            # We stretch by 10 percent, which is way more than enough.
            for i in range(bitlen // (10*32)):
                bit_ticks[pos:pos+32] = tick_pattern
                bits[pos:pos+32] = fill_pattern
                pos += 32
        else:
            # Splice is not at the index. We will write more than one
            # revolution, and terminate the second revolution at the splice.
            # For the first revolution we repeat the track header *backwards*
            # to the very start of the write. This is in case the drive motor
            # spins slower than expected and the write ends before the original
            # splice position.
            # Thus if the drive spins slow, the track gets a longer header.
            bit_ticks += bit_ticks[:self.splice-4]
            bits += bits[:self.splice-4]
            pos = self.splice+4
            fill_pattern = bits[pos:pos+32]
            while pos >= 32:
                pos -= 32
                bits[pos:pos+32] = fill_pattern

        # Convert the stretched track data into flux.
        bit_ticks_i = iter(bit_ticks)
        flux_list = []
        flux_ticks = 0
        for bit in bits:
            flux_ticks += next(bit_ticks_i)
            if bit:
                flux_list.append(flux_ticks)
                flux_ticks = 0
        if flux_ticks:
            flux_list.append(flux_ticks)

        # Package up the flux for return.
        flux = Flux([ticks_to_index], flux_list,
                    self.time_per_rev / ticks_to_index)
        flux.terminate_at_index = splice_at_index
        return flux

 
# Local variables:
# python-indent: 4
# End:
