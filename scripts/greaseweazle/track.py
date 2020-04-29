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
        return len(self.bits) / self.time_per_rev

    # bits: Track bitcell data (bitarray)
    # time_per_rev: Time per revolution, in seconds (float)
    # bit_ticks: Per-bitcell time values, in unitless 'ticks'
    # splice: Location of the track splice, in bitcells, after the index.
    # weak: List of (start, length) weak ranges
    def __init__(self, bits, time_per_rev, bit_ticks=None, splice=0, weak=[]):
        self.bits = bits
        self.time_per_rev = time_per_rev
        self.bit_ticks = bit_ticks
        self.splice = splice
        self.weak = weak

    def __str__(self):
        s = "\nMaster Track: splice at %d\n" % self.splice
        s += (" %d bits, %.1f kbit/s"
              % (len(self.bits), self.bitrate))
        if self.bit_ticks:
            s += " (variable)"
        s += ("\n %.1f ms / rev (%.1f rpm)"
              % (self.time_per_rev * 1000, 60 / self.time_per_rev))
        if len(self.weak) > 0:
            s += "\n %d weak range" % len(self.weak)
            if len(self.weak) > 1: s += "s"
            s += ": " + ", ".join(str(n) for _,n in self.weak) + " bits"
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

        # Weak regions need special processing for correct flux representation.
        for s,n in self.weak:
            e = s + n
            assert s+n <= bitlen
            if n < 2:
                continue
            if n < 400:
                # Short weak regions are written with no flux transitions.
                bits[s:e] = bitarray([0]) * n
            else:
                # Long weak regions we present a fuzzy clock bit in an
                # otherwise normal byte (16 bits MFM). The byte may be
                # interpreted as
                # MFM 0001001010100101 = 12A5 = byte 0x43, or
                # MFM 0001001010010101 = 1295 = byte 0x47
                pattern = bitarray(endian="big")
                pattern.frombytes(b"\x12\xA5")
                bits[s:e] = (pattern * (n//16+1))[:n]
                for i in range(0, n-10, 16):
                    x, y = bit_ticks[s+i+10], bit_ticks[s+i+11]
                    bit_ticks[s+i+10], bit_ticks[s+i+11] = x+y*0.5, y*0.5
            # To prevent corrupting a preceding sync word by effectively
            # starting the weak region early, we start with a 1 if we just
            # clocked out a 0.
            bits[s] = not (bits[-1] if s == 0 else bits[s-1])
            # Similarly modify the last bit of the weak region.
            bits[e-1] = not(bits[e-2] or bits[e%bitlen])
        
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
                    ticks_to_index / self.time_per_rev)
        flux.terminate_at_index = splice_at_index
        return flux

 
# Local variables:
# python-indent: 4
# End:
