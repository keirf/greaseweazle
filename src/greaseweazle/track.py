# greaseweazle/track.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from typing import Any, List, Optional, Tuple, Union, Protocol
import binascii
import itertools as it
from bitarray import bitarray
from greaseweazle.flux import Flux, WriteoutFlux
from greaseweazle import optimised

class PLL:
    def __init__(self, pllspec: str):
        self.period_adj_pct = 5
        self.phase_adj_pct = 60
        self.lowpass_thresh = None
        for x in pllspec.split(':'):
            k,v = x.split('=')
            if k == 'period':
                self.period_adj_pct = int(v)
            elif k == 'phase':
                self.phase_adj_pct = int(v)
            elif k == 'lowpass':
                self.lowpass_thresh = float(v)/1e6
            else:
                raise ValueError()
    def __str__(self) -> str:
        s = ("PLL: period_adj=%d%% phase_adj=%d%%"
             % (self.period_adj_pct, self.phase_adj_pct))
        if self.lowpass_thresh is not None:
            s += (" lowpass_thresh=%.2f" % (self.lowpass_thresh*1e6))
        return s

plls = [
    # Default: An aggressive PLL which will quickly sync to extreme
    # bit timings. For example: long tracks and variable-rate tracks.
    PLL('period=5:phase=60'),
    # Fallback: A conservative PLL which is good at ignoring noise in
    # otherwise fairly well-behaved tracks. For example: high-frequency
    # noise caused by dirt and mould on an old disk.
    PLL('period=1:phase=10')
]

# Precompensation to apply to a MasterTrack for writeout.
class Precomp:
    MFM = 0
    FM  = 1
    GCR = 2
    TYPESTRING = [ 'MFM', 'FM', 'GCR' ]
    def __str__(self) -> str:
        return "Precomp: %s, %dns" % (Precomp.TYPESTRING[self.type], self.ns)
    def __init__(self, type: int, ns: float):
        self.type = type
        self.ns = ns
    def apply(self, bits: bitarray, bit_ticks: List[float],
              scale: float) -> None:
        t = self.ns * scale
        if self.type == Precomp.MFM:
            for i in bits.search(bitarray('10100', endian='big')):
                bit_ticks[i+2] -= t
                bit_ticks[i+3] += t
            for i in bits.search(bitarray('00101', endian='big')):
                bit_ticks[i+2] += t
                bit_ticks[i+3] -= t
        # This is primarily for GCR and FM which permit adjacent 1s (and
        # have correspondingly slower bit times). However it may be useful
        # for illegal MFM sequences too, especially on Amiga (custom syncwords,
        # 4us-bitcell tracks). Normal MFM should not trigger these patterns.
        for i in bits.search(bitarray('110', endian='big')):
            bit_ticks[i+1] -= t
            bit_ticks[i+2] += t
        for i in bits.search(bitarray('011', endian='big')):
            bit_ticks[i+1] += t
            bit_ticks[i+2] -= t

class HasVerify(Protocol):
    verify_revs: float
    def verify_track(self, flux: Flux) -> bool:
        ...

# A pristine representation of a track, from a codec and/or a perfect image.
class MasterTrack:

    # Verify capability may be added "ad hoc" to a MasterTrack object
    verify: Optional[HasVerify] = None

    @property
    def bitrate(self) -> float:
        return len(self.bits) / self.time_per_rev

    def scale(self, factor: float):
        """Scale up index timing by specified factor."""
        self.time_per_rev *= factor

    # bits: Track bitcell data, aligned to the write splice (bitarray or bytes)
    # time_per_rev: Time per revolution, in seconds (float)
    # bit_ticks: Per-bitcell time values, in unitless 'ticks'
    # splice: Location of the track splice, in bitcells, after the index
    # weak: List of (start, length) weak ranges
    # hardsector_bits: Optional list of hard-sector lengths, in bitcells
    def __init__(
            self,
            bits: Union[bitarray, bytes],
            time_per_rev: float,
            bit_ticks: Optional[List[float]] = None,
            splice: int = 0,
            weak: List[Tuple[int,int]] = [],
            hardsector_bits: Optional[List[int]] = None
    ) -> None:
        self.bits: bitarray
        if isinstance(bits, bytes):
            self.bits = bitarray(endian='big')
            self.bits.frombytes(bits)
        else:
            self.bits = bits
        self.time_per_rev = time_per_rev
        self.bit_ticks = bit_ticks
        self.splice = splice
        self.weak = weak
        self.precomp: Optional[Precomp] = None
        self.force_random_weak = True
        self.hardsector_bits = hardsector_bits

    def __str__(self) -> str:
        s = "\nMaster Track: splice @ %d\n" % self.splice
        s += (" %d bits, %.1f kbit/s"
              % (len(self.bits), self.bitrate/1000))
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

    def summary_string(self) -> str:
        s = ('Bitcells (%d bits, %.1f kbit/s, %.1f rpm'
             % (len(self.bits), self.bitrate/1000, 60 / self.time_per_rev))
        if self.bit_ticks:
            s += ', variable'
        if len(self.weak) > 0:
            s += ', weak'
        s += ')'
        return s

    def reverse(self) -> None:
        bitlen = len(self.bits)
        if bitlen == 0: return
        self.bits.reverse()
        if self.bit_ticks is not None:
            self.bit_ticks.reverse()
        self.splice = -self.splice % bitlen
        self.weak = list(map(lambda x: (-x[0] % bitlen, x[1]), self.weak))
        if self.hardsector_bits is not None:
            self.hardsector_bits.reverse()

    def flux(self, revs: Optional[int] = None) -> Flux:
        flux = self._flux(for_writeout=False, cue_at_index=True, revs=revs)
        assert isinstance(flux, Flux)
        return flux

    def flux_for_writeout(self, cue_at_index) -> WriteoutFlux:
        wflux = self._flux(for_writeout=True, cue_at_index=cue_at_index)
        assert isinstance(wflux, WriteoutFlux)
        return wflux

    def _flux(self,
              for_writeout: bool,
              cue_at_index: bool,
              revs: Optional[int] = None
        ) -> Union[Flux, WriteoutFlux]:

        # We're going to mess with the track data, so take a copy.
        bits = self.bits.copy()
        bitlen = len(bits)

        # Also copy the bit_ticks array (or create a dummy one), and remember
        # the total ticks that it contains.
        bit_ticks = self.bit_ticks.copy() if self.bit_ticks else [1] * bitlen
        ticks_to_index = sum(bit_ticks)

        # Weak regions need special processing for correct flux representation.
        for s, n in self.weak:
            if n < 2: continue # Too short to reliably weaken
            e = s + n
            assert 0 <= s < e <= bitlen
            pattern = bitarray(endian="big")
            if n < 400 or self.force_random_weak:
                # Short weak regions are written with no flux transitions.
                # Actually we insert a flux transition every 32 bitcells, else
                # we risk triggering Greaseweazle's No Flux Area generator.
                pattern.frombytes(b"\x80\x00\x00\x00")
                bits[s:e] = (pattern * (n//32+1))[:n]
            else:
                # Long weak regions we present a fuzzy clock bit in an
                # otherwise normal byte (16 bits MFM). The byte may be
                # interpreted as
                # MFM 0001001010100101 = 12A5 = byte 0x43, or
                # MFM 0001001010010101 = 1295 = byte 0x47
                pattern.frombytes(b"\x12\xA5")
                bits[s:e] = (pattern * (n//16+1))[:n]
                for i in range(0, n-10, 16):
                    x, y = bit_ticks[s+i+10], bit_ticks[s+i+11]
                    bit_ticks[s+i+10], bit_ticks[s+i+11] = x+y*0.5, y*0.5
            # To prevent corrupting a preceding sync word by effectively
            # starting the weak region early, we start with a 1 if we just
            # clocked out a 0.
            bits[s] = not bits[s-1]
            # Similarly modify the last bit of the weak region.
            bits[e-1] = not(bits[e-2] or bits[e % bitlen])

        if cue_at_index:
            # Rotate data to start at the index.
            index = -self.splice % bitlen
            if index != 0:
                bits = bits[index:] + bits[:index]
                bit_ticks = bit_ticks[index:] + bit_ticks[:index]
            splice_at_index = index < 4 or bitlen - index < 4
        else:
            assert for_writeout
            splice_at_index = False

        if not for_writeout:
            # Do not extend the track for reliable writeout to disk.
            pass
        elif not cue_at_index:
            # We write the track wherever it may fall (uncued).
            # We stretch the track with extra header gap bytes, in case the
            # drive spins slow and we need more length to create an overlap.
            # Thus if the drive spins slow, the track gets a longer header.
            pos = 4
            # We stretch by 10 percent, which is way more than enough.
            rep = bitlen // (10 * 32)
            bit_ticks = bit_ticks[pos:pos+32] * rep + bit_ticks[pos:]
            bits = bits[pos:pos+32] * rep + bits[pos:]
        elif splice_at_index:
            # Splice is at the index (or within a few bitcells of it).
            # We stretch the track with extra footer gap bytes, in case the
            # drive motor spins slower than expected and we need more filler
            # to get us to the index pulse (where the write will terminate).
            # Thus if the drive spins slow, the track gets a longer footer.
            pos = (self.splice - 4) % bitlen
            # We stretch by 10 percent, which is way more than enough.
            rep = bitlen // (10 * 32)
            bit_ticks = bit_ticks[:pos] + bit_ticks[pos-32:pos] * rep
            bits = bits[:pos] + bits[pos-32:pos] * rep
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

        if for_writeout and self.precomp is not None:
            self.precomp.apply(bits, bit_ticks,
                               ticks_to_index / (self.time_per_rev*1e9))

        # Convert the stretched track data into flux.
        bit_ticks_i = iter(bit_ticks)
        flux_list = []
        flux_ticks: float = 0
        for bit in bits:
            flux_ticks += next(bit_ticks_i)
            if bit:
                flux_list.append(flux_ticks)
                flux_ticks = 0

        # Package up WriteoutFlux.
        if for_writeout:
            if flux_ticks:
                flux_list.append(flux_ticks)
            return WriteoutFlux(
                ticks_to_index, flux_list,
                sample_freq = ticks_to_index / self.time_per_rev,
                index_cued = cue_at_index,
                terminate_at_index = splice_at_index)

        # Package up Flux.
        index_list = [ticks_to_index]
        if revs is None:
            # Emit two revolutions if track data crosses the index.
            revs = 1 if splice_at_index else 2
        assert revs is not None and revs > 0
        if revs > 1:
            l = flux_list
            for i in range(revs-1):
                flux_list = l + [flux_ticks+flux_list[0]] + flux_list[1:]
            index_list *= revs
        flux = Flux(index_list, flux_list,
                    sample_freq = ticks_to_index / self.time_per_rev,
                    index_cued = True)
        flux.splice = sum(bit_ticks[:self.splice])
        return flux

class PLLRevolution:
    def __init__(self, nr_bits: int,
                 hardsector_bits: Optional[List[int]] = None) -> None:
        self.nr_bits = nr_bits
        self.hardsector_bits = hardsector_bits

# Track data generated from flux.
class PLLTrack:

    # clock: Expected time per raw bitcell, in seconds (float)
    # data: Flux object, or a form convertible to a Flux object
    # time_per_rev: Expected time per revolution, in seconds (optional, float)
    # lowpass_thresh: Merge short fluxes with adjacent fluxes (optional, float)
    def __init__(self, clock: float, data, time_per_rev=None, pll=None,
                 lowpass_thresh=None):
        self.clock = clock
        self.time_per_rev = time_per_rev
        self.clock_max_adj = 0.10
        if pll is None: pll = plls[0]
        self.pll_period_adj = pll.period_adj_pct / 100
        self.pll_phase_adj = pll.phase_adj_pct / 100
        self.lowpass_thresh = (lowpass_thresh if pll.lowpass_thresh is None
                               else pll.lowpass_thresh)
        self.bitarray = bitarray(endian='big')
        self.timearray: List[float] = []
        self.revolutions: List[PLLRevolution] = []
        self.import_flux_data(data)


    def __str__(self) -> str:
        s = "\nRaw Track: %d revolutions\n" % len(self.revolutions)
        for rev in range(len(self.revolutions)):
            b, _ = self.get_revolution(rev)
            s += "Revolution %u (%u bits): " % (rev, len(b))
            s += str(binascii.hexlify(b.tobytes())) + "\n"
        b = self.bitarray[sum([x.nr_bits for x in self.revolutions]):]
        s += "Tail (%u bits): " % (len(b))
        s += str(binascii.hexlify(b.tobytes())) + "\n"
        return s[:-1]


    def get_revolution(self, nr) -> Tuple[bitarray, List[float]]:
        start = sum([x.nr_bits for x in self.revolutions[:nr]])
        end = start + self.revolutions[nr].nr_bits
        return self.bitarray[start:end], self.timearray[start:end]


    def get_all_data(self) -> Tuple[bitarray, List[float]]:
        return self.bitarray, self.timearray


    def import_flux_data(self, data) -> None:

        flux = data.flux()
        freq = flux.sample_freq
        if self.time_per_rev is not None:
            # Adjust the raw flux to have the expected time per revolution.
            freq *= flux.time_per_rev / self.time_per_rev

        clock = self.clock
        clock_min = self.clock * (1 - self.clock_max_adj)
        clock_max = self.clock * (1 + self.clock_max_adj)

        index_iter = it.chain(iter(map(lambda x: x/freq, flux.index_list)),
                              [float('inf')])

        if self.lowpass_thresh is not None:
            # Short fluxes below the threshold are merged together, and with
            # adjacent fluxes. The scenario discussed in issue #325 is that
            # a long flux (>=10us) gets a single short flux-reversal pair 
            # inserted in the middle by drive electronics. So all we really
            # need to filter in practice is:
            #   (Long),(Short),(Long) -> (Long+Short+Long)
            # Sequences of short pulses have not been seen in real disk dumps.
            flux_list, thresh = [0.0], self.lowpass_thresh
            flux_iter = iter(flux.list)
            while (x := next(flux_iter, None)) is not None:
                if x/freq <= thresh:
                    y = next(flux_iter, 0.0)
                    # Merge a group-of-three centred on shortest of {x, y}.
                    if y <= x:
                        flux_list.append(x + y + next(flux_iter, 0.0))
                    else:
                        flux_list[-1] += x + y
                else:
                    flux_list.append(x)
        else:
            flux_list = flux.list

        # Make sure there's enough time in the flux list to cover all
        # revolutions by appending a "large enough" final flux value.
        tail = max(0, sum(flux.index_list) - sum(flux_list) + clock*freq*2)
        flux_iter = it.chain(flux_list, [tail])

        revolutions: List[int] = []
        try:
            optimised.flux_to_bitcells(
                self.bitarray, self.timearray, revolutions,
                index_iter, flux_iter,
                freq, clock, clock_min, clock_max,
                self.pll_period_adj, self.pll_phase_adj)
        except AttributeError:
            flux_to_bitcells(
                self.bitarray, self.timearray, revolutions,
                index_iter, flux_iter,
                freq, clock, clock_min, clock_max,
                self.pll_period_adj, self.pll_phase_adj)

        hardsector_bits = None
        for i, nr_bits in enumerate(revolutions):
            if flux.sector_list is not None:
                start = sum(revolutions[:i])
                cell_sum = it.accumulate(self.timearray[start:start+nr_bits])
                hardsector_bits = []
                for sector_end in it.accumulate(map(lambda x: x/freq,
                                                    flux.sector_list[i])):
                    nbits = 0
                    try:
                        while next(cell_sum) < sector_end:
                            nbits += 1
                        nbits += 1
                    except StopIteration:
                        pass
                    hardsector_bits.append(nbits)
            self.revolutions.append(PLLRevolution(nr_bits, hardsector_bits))


def flux_to_bitcells(bit_array, time_array, revolutions,
                     index_iter, flux_iter,
                     freq, clock_centre, clock_min, clock_max,
                     pll_period_adj, pll_phase_adj) -> None:

    nbits = 0
    ticks = 0.0
    clock = clock_centre
    to_index = next(index_iter)

    for x in flux_iter:

        # Gather enough ticks to generate at least one bitcell.
        ticks += x / freq
        if ticks < clock/2:
            continue

        # Clock out zero or more 0s, followed by a 1.
        zeros = 0
        while True:
            ticks -= clock
            if ticks < clock/2:
                break
            zeros += 1
            bit_array.append(False)
        bit_array.append(True)

        # PLL: Adjust clock window position according to phase mismatch.
        new_ticks = ticks * (1 - pll_phase_adj)

        # Distribute the clock adjustment across all bits we just emitted.
        _clock = clock + (ticks - new_ticks) / (zeros + 1)
        for i in range(zeros + 1):
            # Check if we cross the index mark.
            to_index -= _clock
            if to_index < 0:
                revolutions.append(nbits)
                nbits = 0
                to_index += next(index_iter)
            # Emit bit time.
            nbits += 1
            time_array.append(_clock)

        # PLL: Adjust clock frequency according to phase mismatch.
        if zeros <= 3:
            # In sync: adjust clock by a fraction of the phase mismatch.
            clock += ticks * pll_period_adj
        else:
            # Out of sync: adjust clock towards centre.
            clock += (clock_centre - clock) * pll_period_adj
        # Clamp the clock's adjustment range.
        clock = min(max(clock, clock_min), clock_max)

        ticks = new_ticks

# Local variables:
# python-indent: 4
# End:
