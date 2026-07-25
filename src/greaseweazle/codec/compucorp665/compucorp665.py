# greaseweazle/codec/compucorp665/compucorp665.py
#
# Compucorp 665 / METRIC-85 hard-sector floppy disk codec.
#
# Encoding (KryoFlux analysis, 2026):
#   - MFM, 250 kbps (T = 4 µs; PLLTrack clock = 2 µs)
#   - 300 RPM, 16 hard sectors + 1 track index
#   - 256 bytes per sector
#   - NOT IBM MFM (no A1A1A1 address marks)
#   - Payload bytes are bit-reversed vs MSB-first MFM decode (SIO LSB-first)
#
# Sector structure (MFM-decoded bytes, before payload bit-reversal):
#   ~42×00     preamble (all-T clock-only flux)
#   00 01 4A   sync on even cylinders (01 4B on odd)
#   2 bytes    address (addr0 = bitrev8(cyl>>1) | (sec&1))
#   C1 E9 / 5A 06 / 0A AC / …  magic (disk-dependent; decode accepts any)
#   2 bytes    header checksum (poly unknown)
#   6×00       filler
#   1 byte     mark (varies)
#   32×FF      gap
#   ~12 bits   phase nudge before payload
#   256 bytes  sector data (then bit-reverse each byte)
#   2 bytes    data CRC (poly unknown; accepted without check)
#
# This is free and unencumbered software released into the public domain.

from typing import List, Optional, Tuple
import itertools as it
from bitarray import bitarray

from greaseweazle import error
from greaseweazle.codec import codec
from greaseweazle.codec.ibm.ibm import decode, encode, mfm_encode
from greaseweazle.track import MasterTrack, PLL, PLLTrack
from greaseweazle.flux import HasFlux

default_revs = 1

bad_sector = b'-=[BAD SECTOR]=-'

# Sync: 00 01 4A (even cyl) / 00 01 4B (odd cyl). Low bit of third byte = cyl&1.
_sync_4a = bitarray(endian='big')
_sync_4a.frombytes(mfm_encode(encode(b'\x00\x01\x4a')))
_sync_4b = bitarray(endian='big')
_sync_4b.frombytes(mfm_encode(encode(b'\xff\x01\x4b')))
_sync_4b_00 = bitarray(endian='big')
_sync_4b_00.frombytes(mfm_encode(encode(b'\x00\x01\x4b')))
_sync_4a_ff = bitarray(endian='big')
_sync_4a_ff.frombytes(mfm_encode(encode(b'\xff\x01\x4a')))
_SYNCS = [_sync_4a, _sync_4b_00, _sync_4a_ff, _sync_4b]

# Header magic after the address field. Observed values vary by disk
# (BootDisk C1 E9, disk5 5A 06, minnestest 0A AC, …). Used as write default only;
# decode accepts any non-garbage magic when the FF/00 gap also validates.
_MAGIC = b'\xc1\xe9'


# Bytes from start of sync (00 01 4A) through mark, before the 32×FF gap:
#   00 01 4A | addr(2) | magic(2) | hdr_crc(2) | 00×6 | mark(1)  = 17 bytes
_HEADER_LEN = 17

# 0xFF (or phase-flipped 0x00) gap between mark and data.
_PRE_DATA_FF = 32

# Payload phase candidates (MFM half-cells after the FF gap). 12 is the
# usual lock; 11/13 cover residual clock/data slips across sectors.
_DATA_NUDGES = (11, 12, 13)


def _bitrev8(x: int) -> int:
    x &= 0xff
    x = ((x & 0xaa) >> 1) | ((x & 0x55) << 1)
    x = ((x & 0xcc) >> 2) | ((x & 0x33) << 2)
    return ((x >> 4) | (x << 4)) & 0xff


def _bitrev_bytes(data: bytes) -> bytes:
    return bytes(_bitrev8(b) for b in data)


def _expected_addr0(cyl: int, sec_id: int) -> int:
    return _bitrev8(cyl >> 1) | (sec_id & 1)


def _payload_score(data: bytes) -> Tuple[int, int]:
    """Score a candidate payload: (longest_ascii_run, printable_count)."""
    best_run = 0
    run = 0
    printable = 0
    for b in data:
        if 32 <= b < 127:
            printable += 1
            run += 1
            if run > best_run:
                best_run = run
        else:
            run = 0
    return best_run, printable


def _magic_plausible(magic: bytes) -> bool:
    """Reject magics that are typical of false sync hits in FF gaps / noise."""
    if len(magic) != 2:
        return False
    # All-ones / all-zeros show up in gap and empty regions, not real headers.
    if magic in (b'\xff\xff', b'\x00\x00'):
        return False
    return True


class Compucorp665(codec.Codec):
    """Compucorp 665 / METRIC-85 hard-sector MFM disk codec.

    16 sectors per track, 256 bytes per sector, 300 RPM, MFM at 250 kbps.
    """

    time_per_rev = 0.2      # 200 ms / revolution (300 RPM)
    verify_revs: float = default_revs

    def __init__(self, cyl: int, head: int, config):
        self.cyl = cyl
        self.head = head
        self.config = config
        # PLLTrack clock = T/2 = 2 µs for MFM at 250 kbps (T = 4 µs).
        self.clock = 2e-6
        self.bps = 256
        self.sector: List[Optional[bytes]] = [None] * self.nsec

    @property
    def nsec(self) -> int:
        return 16

    def summary_string(self) -> str:
        nsec, nbad = self.nsec, self.nr_missing()
        return 'Compucorp 665 (%d/%d sectors)' % (nsec - nbad, nsec)

    def add(self, sec_id: int, data: bytes) -> None:
        assert not self.has_sec(sec_id)
        self.sector[sec_id] = data

    def has_sec(self, sec_id: int) -> bool:
        return self.sector[sec_id] is not None

    def nr_missing(self) -> int:
        return sum(1 for s in self.sector if s is None)

    def get_img_track(self) -> bytearray:
        tdat = bytearray()
        for sec in self.sector:
            tdat += sec if sec is not None else bad_sector * (self.bps // 16)
        return tdat

    def set_img_track(self, tdat: bytes) -> int:
        totsize = self.nsec * self.bps
        if len(tdat) < totsize:
            tdat += bytes(totsize - len(tdat))
        for sec_id in range(self.nsec):
            self.sector[sec_id] = tdat[sec_id * self.bps:(sec_id + 1) * self.bps]
        return totsize

    # ------------------------------------------------------------------
    # Flux decoding
    # ------------------------------------------------------------------

    @staticmethod
    def _identify_hard_sectors_robust(flux) -> None:
        """Robust replacement for flux.identify_hard_sectors().

        Uses a median-based short/long threshold so glitches at capture start
        (or starting on a short index gap) do not break sector grouping.
        """
        ivs = flux.index_list
        if not ivs or len(ivs) < 4:
            flux.identify_hard_sectors()
            return

        sorted_ivs = sorted(ivs)
        n = len(sorted_ivs)
        median = (sorted_ivs[n // 2] + sorted_ivs[(n - 1) // 2]) / 2
        thresh = median * 0.75

        flux.cue_at_index()
        ticks_to_index = 0.0
        short_ticks = 0.0
        short_count = 0
        sectors: list = []
        new_index_list = []
        new_sector_list = []

        for t in flux.index_list:
            is_short = t < thresh
            if is_short:
                short_ticks += t
                short_count += 1
            if short_count != 0 and (short_count > 1 or not is_short):
                ticks_to_index += short_ticks
                sectors.append(short_ticks)
                new_index_list.append(ticks_to_index)
                new_sector_list.append(sectors)
                sectors = []
                short_ticks = 0.0
                ticks_to_index = 0.0
                short_count = 0
            if not is_short:
                ticks_to_index += t
                sectors.append(t)

        if not new_index_list:
            flux.identify_hard_sectors()
            return

        flux.index_list = new_index_list
        flux.sector_list = new_sector_list
        flux.index_cued = (
            len(new_index_list) >= 2
            and len(new_sector_list[0]) == len(new_sector_list[1])
        )

    def decode_flux(self, track: HasFlux, pll: Optional[PLL] = None) -> None:
        flux = track.flux()
        if flux.time_per_rev < self.time_per_rev / 2:
            self._identify_hard_sectors_robust(flux)
        flux.cue_at_index()

        raw = PLLTrack(time_per_rev=self.time_per_rev,
                       clock=self.clock, data=flux, pll=pll)

        for rev in range(len(raw.revolutions)):
            if self.nr_missing() == 0:
                break
            self._decode_revolution(raw, rev)

    def _decode_revolution(self, raw: PLLTrack, rev: int) -> None:
        bits, _ = raw.get_revolution(rev)
        # Sector 15 can extend a few hundred bits past the revolution boundary.
        if rev + 1 < len(raw.revolutions):
            next_bits, _ = raw.get_revolution(rev + 1)
            bits = bits + next_bits[:8000]

        hs = raw.revolutions[rev].hardsector_bits
        if hs is not None:
            hs = list(it.accumulate(hs))
            if len(hs) == self.nsec:
                hs = [0] + hs + [len(bits)]
            elif len(hs) == self.nsec + 1:
                # 17 pulses: first is track index — discard it.
                hs = [hs[0]] + hs[1:] + [len(bits)]
            else:
                return
        else:
            # Equal-length virtual sectors when the dump has no hard-sector
            # indexes (soft index only). range(nsec+1) already includes 0 and
            # len(bits) — do not prepend an extra 0 (that made sector 0 empty).
            hs = [len(bits) * i // self.nsec for i in range(self.nsec + 1)]

        for sec_id in range(self.nsec):
            if self.has_sec(sec_id):
                continue
            self._try_decode_sector(bits, hs[sec_id], hs[sec_id + 1], sec_id)

    def _try_decode_sector(self, bits, s: int, e: int, sec_id: int) -> None:
        """Find 00 01 4A/4B sync, verify header, extract 256-byte payload."""
        # Sync sits ~700 MFM bits after the sector hole (after ~42×00 preamble).
        _SYNC_MIN_BIT = 400
        _SYNC_MAX_BIT = 1600

        sec_bits = bits[s:e]
        hits = []
        for syn in _SYNCS:
            for pos in sec_bits.search(syn):
                if _SYNC_MIN_BIT <= pos <= _SYNC_MAX_BIT:
                    hits.append(pos)
        hits.sort()

        for off in hits:
            if self._extract_at_sync(sec_bits, off, sec_id):
                return

    def _extract_at_sync(self, sec_bits, off: int, sec_id: int) -> bool:
        """Decode header at sync bit offset; on success store sector data."""
        # Need sync + header + FF gap + max nudge + data + CRC.
        need = ((_HEADER_LEN + _PRE_DATA_FF) * 16
                + max(_DATA_NUDGES) + (self.bps + 2) * 16)
        if off + need > len(sec_bits):
            return False

        hdr = decode(sec_bits[off:off + _HEADER_LEN * 16].tobytes())
        if len(hdr) < _HEADER_LEN:
            return False

        # hdr: 00 01 4A/4B | addr0 addr1 | magic | crc_hi crc_lo | 00×6 | mark
        if hdr[0] != 0x00 or hdr[1] != 0x01 or hdr[2] not in (0x4a, 0x4b):
            return False
        magic = bytes(hdr[5:7])
        if not _magic_plausible(magic):
            return False
        # Boot disks encode cyl parity in sync[2] LSB; some disks always use 4A.
        # Only enforce parity for the BootDisk magic.
        if magic == b'\xc1\xe9' and (hdr[2] & 1) != (self.cyl & 1):
            return False

        gap = decode(sec_bits[off + _HEADER_LEN * 16:
                              off + (_HEADER_LEN + _PRE_DATA_FF) * 16].tobytes())
        if len(gap) < _PRE_DATA_FF:
            return False
        n_ff = sum(1 for b in gap if b == 0xff)
        n_00 = sum(1 for b in gap if b == 0x00)
        if max(n_ff, n_00) < _PRE_DATA_FF - 4:
            return False

        # Try nearby phase nudges; keep the payload with the best ASCII score
        # after LSB-first bit-reversal (matches Z80-SIO byte order).
        gap_base = off + (_HEADER_LEN + _PRE_DATA_FF) * 16
        best_data = None
        best_score = (-1, -1)
        best_nudge = -1
        for nudge in _DATA_NUDGES:
            raw = sec_bits[gap_base + nudge:
                           gap_base + nudge + (self.bps + 2) * 16]
            if len(raw) < (self.bps + 2) * 16:
                continue
            data_and_crc = decode(raw.tobytes())
            if len(data_and_crc) < self.bps:
                continue
            data = _bitrev_bytes(bytes(data_and_crc[:self.bps]))
            score = _payload_score(data)
            if (score > best_score
                    or (score == best_score and nudge == 12)
                    or (score == best_score and best_nudge != 12
                        and nudge < best_nudge)):
                best_score = score
                best_data = data
                best_nudge = nudge

        if best_data is None:
            return False
        self.add(sec_id, best_data)
        return True

    # ------------------------------------------------------------------
    # Track generation (for writing / verification)
    # ------------------------------------------------------------------

    def master_track(self) -> MasterTrack:
        """Encode all sectors back to an MFM bit stream for writing."""
        slen = int(self.time_per_rev / self.clock / self.nsec / 16)

        encoded_sectors = bytes()
        for sec_id in range(self.nsec):
            sector = self.sector[sec_id]
            if sector is None:
                sector = bad_sector * (self.bps // 16)

            sync3 = 0x4a | (self.cyl & 1)
            addr0 = _expected_addr0(self.cyl, sec_id)
            # On disk the payload is stored bit-reversed relative to host bytes.
            disk_data = _bitrev_bytes(sector)
            raw = (
                bytes(42)                          # preamble
                + bytes([0x00, 0x01, sync3, addr0, 0x00])
                + _MAGIC
                + bytes(2)                         # header CRC placeholder
                + bytes(6)                         # filler
                + b'\x01'                          # mark
                + b'\xff' * _PRE_DATA_FF
                + disk_data
                + bytes(2)                         # data CRC placeholder
            )

            s = encode(raw)
            s += encode(bytes(max(0, slen - len(s) // 2)))
            encoded_sectors += s

        mfm_bits = mfm_encode(encoded_sectors)

        hardsector_bits = [slen * 16] * self.nsec
        track = MasterTrack(bits=mfm_bits,
                            time_per_rev=self.time_per_rev,
                            hardsector_bits=hardsector_bits)
        track.verify = self
        return track

    def verify_track(self, flux) -> bool:
        rb = self.__class__(self.cyl, self.head, self.config)
        rb.decode_flux(flux)
        return rb.nr_missing() == 0 and self.sector == rb.sector


class Compucorp665Def(codec.TrackDef):

    default_revs = default_revs

    def __init__(self, format_name: str):
        self.finalised = False

    def add_param(self, key: str, val) -> None:
        raise error.Fatal('unrecognised track option %s for compucorp665' % key)

    def finalise(self) -> None:
        self.finalised = True

    def mk_track(self, cyl: int, head: int) -> Compucorp665:
        return Compucorp665(cyl, head, self)


# Local variables:
# python-indent: 4
# End:
