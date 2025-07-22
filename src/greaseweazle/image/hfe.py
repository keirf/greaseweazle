# greaseweazle/image/hfe.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from __future__ import annotations
from typing import cast, Dict, Tuple, Optional, List

import struct
import itertools as it

from greaseweazle import error
from greaseweazle.tools import util
from greaseweazle.codec import codec
from greaseweazle.codec.ibm import ibm
from greaseweazle.codec.apple2 import apple2_gcr
from greaseweazle.track import MasterTrack, PLLTrack
from bitarray import bitarray
from .image import Image, ImageOpts

InterfaceMode = {
    'IBMPC_DD':             0x00,
    'IBMPC_HD':             0x01,
    'ATARIST_DD':           0x02,
    'ATARIST_HD':           0x03,
    'AMIGA_DD':             0x04,
    'AMIGA_HD':             0x05,
    'CPC_DD':               0x06,
    'GENERIC_SHUGART_DD':   0x07,
    'IBMPC_ED':             0x08,
    'MSX2_DD':              0x09,
    'C64_DD':               0x0A,
    'EMU_SHUGART':          0x0B,
    'S950_DD':              0x0C,
    'S950_HD':              0x0D,
    'S950_DD_HD':           0x0E,
    'IBMPC_DD_HD':          0x0F,
    'QUICKDISK':            0x10,
    'UNKNOWN':              0xFF
}

EncodingType = {
    'ISOIBM_MFM':           0x00,
    'AMIGA_MFM':            0x01,
    'ISOIBM_FM':            0x02,
    'EMU_FM':               0x03,
    'TYCOM_FM':             0x04,
    'MEMBRAIN_MFM':         0x05,
    'APPLEII_GCR1':         0x06,
    'APPLEII_GCR2':         0x07,
    'APPLEII_HDDD_A2_GCR1': 0x08,
    'APPLEII_HDDD_A2_GCR2': 0x09,
    'ARBURGDAT':            0x0A,
    'ARBURGSYS':            0x0B,
    'AED6200P_MFM':         0x0C,
    'NORTHSTAR_HS_MFM':     0x0D,
    'HEATHKIT_HS_FM':       0x0E,
    'DEC_RX02_M2FM':        0x0F,
    'APPLEMAC_GCR':         0x10,
    'QD_MO5':               0x11,
    'C64_GCR':              0x12,
    'VICTOR9K_GCR':         0x13,
    'MICRALN_HS_FM':        0x14,
    'UNKNOWN':              0xFF
}

class HFEOpts(ImageOpts):
    """bitrate: Bitrate of new HFE image file.
    """

    w_settings = [ 'bitrate', 'version', 'interface', 'encoding',
                   'double_step', 'uniform' ]

    def __init__(self) -> None:
        self._bitrate: Optional[int] = None
        self._version = 1
        self._interface = 0xff
        self._encoding = 0xff
        self.double_step = False
        self.uniform = False

    @property
    def bitrate(self) -> Optional[int]:
        return self._bitrate
    @bitrate.setter
    def bitrate(self, bitrate: float):
        try:
            self._bitrate = int(bitrate)
            if self._bitrate <= 0:
                raise ValueError
        except ValueError:
            raise error.Fatal("HFE: Invalid bitrate: '%s'" % bitrate)

    @property
    def version(self) -> int:
        return self._version
    @version.setter
    def version(self, version) -> None:
        try:
            self._version = int(version)
            if self._version != 1 and self._version != 3:
                raise ValueError
        except ValueError:
            raise error.Fatal("HFE: Invalid version: '%s'" % version)

    @property
    def interface(self):
        return self._interface
    @interface.setter
    def interface(self, mode):
        try:
            self._interface = InterfaceMode[mode.upper()]
        except KeyError:
            try:
                self._interface = int(mode, 0)
            except ValueError:
                l = [ x.lower() for x in InterfaceMode.keys() ]
                l.sort()
                raise error.Fatal("Bad HFE interface mode: '%s'\n" % mode
                                  + 'Valid modes:\n' + util.columnify(l))

    @property
    def encoding(self):
        return self._encoding
    @encoding.setter
    def encoding(self, enc):
        try:
            self._encoding = EncodingType[enc.upper()]
        except KeyError:
            try:
                self._encoding = int(enc, 0)
            except ValueError:
                l = [ x.lower() for x in EncodingType.keys() ]
                l.sort()
                raise error.Fatal("Bad HFE encoding type: '%s'\n" % enc
                                  +  'Valid types:\n' + util.columnify(l))

class HFETrack:
    def __init__(self, track: MasterTrack) -> None:
        self.track = track

    @classmethod
    def from_bitarray(cls, bits: bitarray, bitrate: int) -> HFETrack:
        return cls(MasterTrack(
            bits = bits, time_per_rev = len(bits) / (2000*bitrate)))

    @classmethod
    def from_hfe_bytes(cls, b: bytes, bitrate: int) -> HFETrack:
        bits = bitarray(endian='big')
        bits.frombytes(b)
        bits.bytereverse()
        return cls.from_bitarray(bits, bitrate)

    def to_hfe_bytes(self) -> bytes:
        bits = bitarray(endian='big')
        bits.frombytes(self.track.bits.tobytes())
        bits.bytereverse()
        return bits.tobytes()


class HFE(Image):

    opts: HFEOpts

    def __init__(self, name: str, _fmt) -> None:
        self.opts = HFEOpts()
        self.filename = name
        # Each track is (bitlen, rawbytes).
        # rawbytes is a bytes() object in little-endian bit order.
        self.to_track: Dict[Tuple[int,int], HFETrack] = dict()


    def from_bytes(self, dat: bytes) -> None:

        (sig, f_rev, n_cyl, n_side, t_enc, bitrate,
         _, _, _, tlut_base) = struct.unpack("<8s4B2H2BH", dat[:20])
        if sig == b"HXCHFEV3":
            version = 3
        else:
            error.check(sig == b"HXCPICFE", "Not a valid HFE file")
            version = 1
        error.check(f_rev <= 1, "Not a valid HFE file")
        error.check(0 < n_cyl, "HFE: Invalid #cyls")
        error.check(0 < n_side < 3, "HFE: Invalid #sides")

        self.opts.bitrate = bitrate
        self.opts.version = version

        tlut = dat[tlut_base*512:tlut_base*512+n_cyl*4]
        
        for cyl in range(n_cyl):
            for side in range(n_side):
                offset, length = struct.unpack("<2H", tlut[cyl*4:(cyl+1)*4])
                todo = length // 2
                tdat = bytes()
                while todo:
                    d_off = offset*512 + side*256
                    d_nr = 256 if todo > 256 else todo
                    tdat += dat[d_off:d_off+d_nr]
                    todo -= d_nr
                    offset += 1
                track_v1 = HFETrack.from_hfe_bytes(tdat, bitrate)
                if version == 1:
                    self.to_track[cyl,side] = track_v1
                else:
                    self.to_track[cyl,side] = hfev3_mk_track(
                        cyl, side, track_v1)


    def get_track(self, cyl: int, side: int) -> Optional[MasterTrack]:
        if (cyl,side) not in self.to_track:
            return None
        return self.to_track[cyl,side].track


    def emit_track(self, cyl: int, side: int, track) -> None:
        # HFE convention is that FM and GCR are recorded at double rate
        double_rate = (
            (isinstance(track, ibm.IBMTrack) and track.mode is ibm.Mode.FM)
            or isinstance(track, apple2_gcr.Apple2GCR))
        t = track.master_track() if isinstance(track, codec.Codec) else track
        if self.opts.bitrate is None:
            error.check(hasattr(t, 'bitrate'),
                        'HFE: Requires bitrate to be specified'
                        ' (eg. filename.hfe::bitrate=500)')
            self.opts.bitrate = round(t.bitrate / 2e3)
            assert self.opts.bitrate is not None # mypy
            if double_rate:
                self.opts.bitrate *= 2
            print('HFE: Data bitrate detected: %d kbit/s' % self.opts.bitrate)
        if isinstance(t, MasterTrack):
            # Rotate data and timings to start at the index.
            index = -t.splice % len(t.bits)
            bits = t.bits[index:] + t.bits[:index]
            bit_ticks = (t.bit_ticks[index:] + t.bit_ticks[:index]
                         if t.bit_ticks else None)
            hardsector_bits = t.hardsector_bits
            # Rotate the weak areas
            weak = []
            for s, n in t.weak:
                s -= t.splice
                if s < 0:
                    if s + n > 0:
                        weak.append((s % len(t.bits), -s))
                        weak.append((0, s + n))
                    else:
                        weak.append((s % len(t.bits), n))
                else:
                    weak.append((s, n))
            if double_rate:
                double_bytes = ibm.doubler(bits.tobytes())
                double_bits = bitarray(endian='big')
                double_bits.frombytes(double_bytes)
                bits = double_bits[:2*len(bits)]
                if bit_ticks is not None:
                    bit_ticks = [x for x in bit_ticks for _ in range(2)]
                weak = [(2*x,2*y) for (x,y) in weak]
                if hardsector_bits is not None:
                    hardsector_bits = [2*x for x in hardsector_bits]
            mt = MasterTrack(
                bits = bits, time_per_rev = t.time_per_rev,
                bit_ticks = bit_ticks, weak = weak,
                hardsector_bits = hardsector_bits)
        else:
            flux = t.flux()
            flux.cue_at_index()
            raw = PLLTrack(clock = 5e-4 / self.opts.bitrate, data = flux)
            bits, bit_ticks = raw.get_revolution(0)
            if self.opts.uniform:
                bit_ticks = None
            mt = MasterTrack(
                bits = bits, time_per_rev = flux.time_per_rev,
                bit_ticks = bit_ticks,
                hardsector_bits = raw.revolutions[0].hardsector_bits)
        self.to_track[cyl,side] = HFETrack(mt)


    def hfev1_get_image(self) -> bytes:

        assert self.opts.version == 1
        assert self.opts.bitrate is not None

        n_side = 1
        n_cyl = max(self.to_track.keys(), default=(0,), key=lambda x:x[0])[0]
        n_cyl += 1

        # We dynamically build the Track-LUT and -Data arrays.
        tlut = bytearray()
        tdat = bytearray()

        # Stuff real data into the image.
        for i in range(n_cyl):
            s0 = self.to_track[i,0] if (i,0) in self.to_track else None
            s1 = self.to_track[i,1] if (i,1) in self.to_track else None
            if s0 is None and s1 is None:
                # Dummy data for empty cylinders. Assumes 300RPM.
                nr_bytes = 100 * self.opts.bitrate
                tlut += struct.pack("<2H", len(tdat)//512 + 2, nr_bytes)
                tdat += bytes([0x88] * (nr_bytes+0x1ff & ~0x1ff))
            else:
                # At least one side of this cylinder is populated.
                if s1 is not None:
                    n_side = 2
                bc = [s0.to_hfe_bytes() if s0 is not None else bytes(),
                      s1.to_hfe_bytes() if s1 is not None else bytes()]
                nr_bytes = max(len(t) for t in bc)
                nr_blocks = (nr_bytes + 0xff) // 0x100
                tlut += struct.pack("<2H", len(tdat)//512 + 2, 2 * nr_bytes)
                for b in range(nr_blocks):
                    for t in bc:
                        slice = t[b*256:(b+1)*256]
                        tdat += slice + bytes([0x88] * (256 - len(slice)))

        # Construct the image header.
        header = struct.pack("<8s4B2H2BH2B",
                             b"HXCPICFE",
                             0,
                             n_cyl,
                             n_side,
                             self.opts.encoding,
                             self.opts.bitrate,
                             0,    # rpm (unused)
                             self.opts.interface,
                             1,    # rsvd
                             1,    # track list offset
                             0xff, # write_allowed
                             0xff if not self.opts.double_step else 0)

        # Pad the header and TLUT to 512-byte blocks.
        header += bytes([0xff] * (0x200 - len(header)))
        tlut += bytes([0xff] * (0x200 - len(tlut)))

        return header + tlut + tdat


    def get_image(self) -> bytes:

        # Empty disk may have no bitrate
        if self.opts.bitrate is None:
            assert not self.to_track
            self.opts.bitrate = 250

        if self.opts.version == 3:
            return hfev3_get_image(self)

        try:
            return self.hfev1_get_image()
        except struct.error as e:
            raise error.Fatal(
                '''\
                HFE: Track too long to fit in image!
                Are you trying to create an ED-rate image?
                If so: You can't. Use another image format.''')


###
### HFE V3 TRACK PARSER
###

class HFEv3_Op:
    Nop      = 0xf0
    Index    = 0xf1
    Bitrate  = 0xf2
    SkipBits = 0xf3
    Rand     = 0xf4

class HFEv3_Range:
    def __init__(self, s: int, n: int, val=0):
        self.s, self.n, self.val = s, n, val
    @property
    def e(self) -> int:
        return self.s + self.n

def hfev3_mk_track(cyl: int, head: int, track_v1: HFETrack) -> HFETrack:

    def add_weak(weak: List[HFEv3_Range], pos: int, nr: int) -> None:
        if len(weak) != 0:
            w = weak[-1]
            if w.e == pos:
                w.n += nr
                return
        weak.append(HFEv3_Range(pos, nr))

    # Input: Raw HFE
    tdat = track_v1.track.bits.tobytes()

    # Outputs: Bitcells, bitcell timings, weak areas.
    bits = bitarray(endian='big')
    ticks: List[int] = []
    weak: List[HFEv3_Range] = []
    index: List[int] = []

    i = rate = 0
    while i < len(tdat):
        x, i = tdat[i], i+1
        if x == HFEv3_Op.Nop:
            pass
        elif x == HFEv3_Op.Index:
            index.append(len(bits))
        elif x == HFEv3_Op.Bitrate:
            if i+1 > len(tdat):
                # Non fatal: This has been observed in HFEv3 images created
                # by HxC tools (see issue #346).
                print(f'T{cyl}.{head}: HFEv3: Truncated bitrate opcode')
                break
            rate, i = tdat[i], i+1
        elif x == HFEv3_Op.SkipBits:
            error.check(i+2 <= len(tdat),
                        f'T{cyl}.{head}: HFEv3: Truncated skipbits opcode')
            nr, x, i = tdat[i], tdat[i+1], i+2
            error.check(0 < nr < 8,
                        f'T{cyl}.{head}: HFEv3: Bad skipbits value: {nr}')
            if x == HFEv3_Op.Rand:
                add_weak(weak, len(bits), 8-nr)
                x = 0
            try:
                bits.frombytes(bytes([x << nr]))
            except ValueError:
                raise error.Fatal(f'T{cyl}.{head}: HFEv3: Bad skipbits: '
                                  f'0x{x:02x}<<{nr} = 0x{x<<nr:04x}')
            bits = bits[:-nr]
            ticks += [rate]*(8-nr)
        elif x == HFEv3_Op.Rand:
            add_weak(weak, len(bits), 8)
            bits.frombytes(bytes(1))
            ticks += [rate]*8
        else:
            error.check((x & 0xf0) != 0xf0,
                        f'T{cyl}.{head}: HFEv3: unrecognised opcode {x:02x}')
            bits.frombytes(bytes([x]))
            ticks += [rate]*8

    # If the track did not start with a Bitrate opcode, cycle the rate round
    # from the end of the track.
    error.check(rate != 0, 'HFEv3: Bitrate was never set in track')
    for i in range(len(ticks)):
        if ticks[i] != 0: break
        ticks[i] = rate

    # This only works if the track is index aligned, with the first sector
    # starting at bit 0.
    hardsector_bits: Optional[List[int]] = None
    if len(index) > 1:
        pos = 0
        hardsector_bits = []
        for x in index[1:]:
            hardsector_bits.append(x-pos)
            pos = x
        # The last index pulse is the pre-index hole: extend to end of track
        hardsector_bits[-1] += len(bits) - pos

    mt = MasterTrack(
        bits = bits,
        time_per_rev = sum(ticks)/36e6,
        bit_ticks = cast(List[float], ticks), # mypy
        weak = list(map(lambda x: (x.s, x.n), weak)),
        hardsector_bits = hardsector_bits
    )
    return HFETrack(mt)


###
### HFE V3 TRACK GENERATOR
###

# HFEv3_Chunk: Represents a consecutive range of input bitcells with identical
# bitcell timings and weakness property.
class HFEv3_Chunk:
    def __init__(self, nbits: int, time_per_bit: float, is_random: bool,
                 emit_index: bool):
        self.nbits = nbits
        self.time_per_bit = time_per_bit
        self.is_random = is_random
        self.emit_index = emit_index
    def __str__(self) -> str:
        s = "%d bits, %.4fus per bit" % (self.nbits, self.time_per_bit*1e6)
        if self.is_random:
            s += ", random"
        return s

class HFEv3_Generator:
    def __init__(self, track: MasterTrack) -> None:
        # Properties of the input track.
        self.track = track
        if track.bit_ticks is not None:
            self.ticks_per_rev = sum(track.bit_ticks)
        else:
            self.ticks_per_rev = len(track.bits)
        self.time_per_tick = track.time_per_rev / self.ticks_per_rev
        # index_positions: Bit positions at which to insert index pulses
        index_positions = track.hardsector_bits
        if not index_positions:
            index_positions = [ 0 ]
        else:
            index_positions[-1] //= 2
            index_positions = list(it.accumulate([ 0 ] + index_positions))
        index_positions.append(len(track.bits))
        self.index_positions = index_positions
        # tick_iter: An iterator over ranges of consecutive bitcells with
        # identical ticks per bitcell.
        self.ticks: List[Tuple[int,int,float]]
        if track.bit_ticks is None:
            self.ticks = [(0,len(track.bits),1)]
        else:
            self.ticks = []
            c, s = track.bit_ticks[0], 0
            for i, t in enumerate(track.bit_ticks):
                if t != c:
                    self.ticks.append((s, i-s, c))
                    c, s = t, i
            self.ticks.append((s, len(track.bit_ticks)-s, c))
        self.tick_iter = map(lambda x: HFEv3_Range(*x),
                             it.chain(self.ticks, [(len(track.bits),0,0)]))
        self.tick_cur = next(self.tick_iter)
        # weak_iter: An iterator over weak ranges.
        self.weak_iter = map(lambda x: HFEv3_Range(*x),
                             it.chain(track.weak, [(len(track.bits),0)]))
        self.weak_cur = next(self.weak_iter)
        # out: The raw HFEv3 output bytestream that we are generating.
        self.out = bytearray()
        # time: Input track current time, in seconds.
        # hfe_time: HFE track output current time, in seconds.
        self.time = self.hfe_time = 0.0
        # pos: Input track current position, in bitcells.
        self.pos = 0
        # rate: Current HFE output rate, as set by HFEv3_Op.Bitrate.
        # rate_change_pos: Byte position we last updated rate in HFE output.
        self.rate, self.rate_change_pos = -1, 0
        # sec: Which sector are we emitting
        self.sec = 0
        # chunk: Chunk of input bitcells currently being processed.
        self.chunk = self.next_chunk()

    def next_chunk(self) -> Optional[HFEv3_Chunk]:
        # All done? Then return nothing.
        if self.pos >= len(self.track.bits):
            return None
        # Position to next sector pulse
        emit_index = False
        while (n := self.index_positions[self.sec] - self.pos) <= 0:
            assert n == 0 and not emit_index
            self.sec += 1
            emit_index = True
        # Position among bitcells with identical timing.
        while self.pos >= self.tick_cur.e:
            self.tick_cur = next(self.tick_iter)
        assert self.pos >= self.tick_cur.s
        n = min(n, self.tick_cur.e - self.pos)
        # Position relative to weak ranges.
        while self.pos >= self.weak_cur.e:
            self.weak_cur = next(self.weak_iter)
        if self.pos < self.weak_cur.s:
            n = min(n, self.weak_cur.s - self.pos)
            is_random = False
        else:
            n = min(n, self.weak_cur.e - self.pos)
            is_random = True
        return HFEv3_Chunk(n, self.time_per_tick * self.tick_cur.val,
                           is_random, emit_index)

    def increment_position(self, n: int) -> None:
        c = self.chunk
        assert c is not None
        self.pos += n
        self.time += n * c.time_per_bit
        self.hfe_time += n * self.rate/36e6
        c.nbits -= n
        if c.nbits == 0:
            self.chunk = self.next_chunk()

    def raw_hfe_bytes(self) -> bytes:
        x = bitarray(endian='big')
        x.frombytes(self.out)
        x.bytereverse()
        return x.tobytes()

    @classmethod
    def empty(cls, time_per_rev: float, bitrate: float) -> HFEv3_Generator:
        nbits = round(2000 * bitrate * time_per_rev)
        return cls(MasterTrack(
            bits = bitarray(nbits),
            time_per_rev = time_per_rev,
            weak = [(0, nbits)]))


def hfev3_get_image(hfe: HFE) -> bytes:

    n_side = 1
    n_cyl = max(hfe.to_track.keys(), default=(0,), key=lambda x:x[0])[0]
    n_cyl += 1

    # We dynamically build the Track-LUT and -Data arrays.
    tlut = bytearray()
    tdat = bytearray()

    try:
        default_time_per_rev = (next(iter(hfe.to_track.values()))
                                .track.time_per_rev)
    except StopIteration:
        default_time_per_rev = 0.2

    bitrate = hfe.opts.bitrate
    assert bitrate is not None

    # Stuff real data into the image.
    for cyl in range(n_cyl):
        time_per_rev = (hfe.to_track[cyl,0].track.time_per_rev
                        if (cyl,0) in hfe.to_track
                        else hfe.to_track[cyl,1].track.time_per_rev
                        if (cyl,1) in hfe.to_track
                        else default_time_per_rev)
        s = list()
        s.append(HFEv3_Generator(hfe.to_track[cyl,0].track)
                 if (cyl,0) in hfe.to_track
                 else HFEv3_Generator.empty(time_per_rev, bitrate))
        s.append(HFEv3_Generator(hfe.to_track[cyl,1].track)
                 if (cyl,1) in hfe.to_track
                 else HFEv3_Generator.empty(time_per_rev, bitrate))

        if (cyl,1) in hfe.to_track:
            n_side = 2

        max_skew, max_delta = 0.0, 0.0
        while True:
            # Select the track 'x' with work to do and shortest output buffer.
            x, y, c = s[0], s[1], s[0].chunk
            if c is None or (len(y.out) < len(x.out) and y.chunk is not None):
                x, y, c = y, x, y.chunk
                if c is None:
                    break

            # Calculate timing error across drive heads, in bitcells.
            # This also accounts for differences in output byte position.
            diff = (round((x.time - y.time) / c.time_per_bit)
                    + (len(y.out) - len(x.out)) * 8)
            max_skew = max(max_skew, abs(diff))

            # Adjust time per bit for accumulated error in time due to
            # rounding error in the HFEv3_Op.Bitrate parameter.
            # Note that we distribute the correction factor across the
            # worst-case number of bitcells before we allow ourselves
            # another minor bitrate adjustment.
            rate_distance = 64 # byte-cells
            tpb = c.time_per_bit + (x.time - x.hfe_time) / (rate_distance*8)

            if c.emit_index:
                c.emit_index = False
                x.out.append(HFEv3_Op.Index)
                diff -= 8

            # Do a rate change if the rate has significantly changed or,
            # for a change of +/-1, if we haven't changed rate in a while.
            rate = round(tpb * 36e6)
            if (rate != x.rate
                and (abs(rate-x.rate) > 1 or diff >= 16
                     or (len(x.out) - x.rate_change_pos) > rate_distance)):
                x.out.append(HFEv3_Op.Bitrate)
                x.out.append(rate)
                x.rate = rate
                x.rate_change_pos = len(x.out)
                diff -= 16

            # Insert Nop padding if we still need it.
            if diff >= 8:
                x.out.append(HFEv3_Op.Nop)

            # Emit up to 8 bitcells.
            n = min(c.nbits, 8)
            if n < 8:
                x.out.append(HFEv3_Op.SkipBits)
                x.out.append(8 - n)
            if c.is_random:
                x.out.append(HFEv3_Op.Rand)
            else:
                # Extract next bitcells into a stream-ready byte.
                b = x.track.bits[x.pos:x.pos+n].tobytes()[0] >> (8-n)
                # If the byte looks like an opcode, skip a bit.
                if (b & 0xf0) == 0xf0:
                    n = 7
                    b >>= 1
                    x.out.append(HFEv3_Op.SkipBits)
                    x.out.append(8 - n)
                # Emit the fixed-up byte.
                x.out.append(b)

            # Update tallies.
            x.increment_position(n)
            max_delta = max(max_delta, abs(x.time - x.hfe_time))

        info = 'HFEv3 [%d] ' % cyl
        for i,x in enumerate(s):
            delta = len(x.out)-len(x.track.bits)//8
            info += ('h%d:%d/+%d/+%.02f%% ' %
                     (i, len(x.out), delta, delta*8*100/len(x.track.bits)))
        info += 'hskew:%dbc rate-err:%.02fus' % (max_skew, max_delta*1e6)
        print(info)

        nr_bytes = max(len(x.out) for x in s)
        error.check(
            nr_bytes < 32768,
            '''\
            HFEv3: Track too long to fit in image!
            Are you trying to convert raw flux (SCP, KF, etc)?
            If so: Try specifying 'uniform': eg. name.hfe::version=3:uniform
                   (will break variable-rate copy protections such as Copylock)
            If not: Report a bug.''')

        nr_blocks = (nr_bytes + 0xff) // 0x100
        for x in s:
            x.out += bytes([HFEv3_Op.Nop]) * (nr_blocks*0x100 - len(x.out))
        bc = [x.raw_hfe_bytes() for x in s]
        tlut += struct.pack("<2H", len(tdat)//512 + 2, 2 * nr_bytes)
        for b in range(nr_blocks):
            for t in bc:
                tdat += t[b*256:(b+1)*256]

    # Construct the image header.
    header = struct.pack("<8s4B2H2BH2B",
                         b"HXCHFEV3",
                         0,
                         n_cyl,
                         n_side,
                         hfe.opts.encoding,
                         hfe.opts.bitrate,
                         0,    # rpm (unused)
                         hfe.opts.interface,
                         1,    # rsvd
                         1,    # track list offset
                         0xff, # write_allowed
                         0xff if not hfe.opts.double_step else 0)

    # Pad the header and TLUT to 512-byte blocks.
    header += bytes([0xff] * (0x200 - len(header)))
    tlut += bytes([0xff] * (0x200 - len(tlut)))

    return header + tlut + tdat

# Local variables:
# python-indent: 4
# End:
