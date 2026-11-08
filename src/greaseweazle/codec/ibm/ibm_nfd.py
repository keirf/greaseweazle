# greaseweazle/codec/ibm/ibm_nfd.py
#
# PC-98 NFD (Rev 1d) support: multi-revolution IBM MFM/FM decoding and
# generic analysis of non-standard disks: CRC errors, DDAM, weak bits
# via cross-revolution diff, duplicate-ID via diagnostic-read records.
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from __future__ import annotations
from typing import Dict, List, Optional, Tuple

from greaseweazle import error
from greaseweazle.track import PLL, PLLTrack

from .ibm import IBMTrack, IBMTrack_FixedDef, Mode, Mark, IAM, IDAM, Sector


class IBMTrack_MultiRev(IBMTrack):
    """IBM FM/MFM track which keeps the sectors decoded from every
    revolution, rather than merging them into one list."""

    def __init__(self, cyl: int, head: int, mode: Mode):
        super().__init__(cyl, head, mode)
        self.rev_sectors: List[Sector] = []
        # IDs for which no revolution decoded a data field.
        self.rev_idams: List[IDAM] = []

    def decode_raw(self, raw: PLLTrack, pll: Optional[PLL], flux) -> None:
        if self.mode is Mode.FM:
            areas = self.fm_decode_raw(raw)
        elif self.mode is Mode.MFM:
            areas = self.mfm_decode_raw(raw)
        else:
            raise error.Fatal(
                'IBMTrack_MultiRev: unsupported mode %s' % self.mode)
        for a in areas:
            if isinstance(a, IAM):
                if not any(abs(iam.start - a.start) < 1000
                           for iam in self.iams):
                    self.iams.append(a)
            elif isinstance(a, Sector):
                # Only merge within a revolution (repeated PLL passes).
                dupe = False
                for i, sec in enumerate(self.rev_sectors):
                    if (sec.revolution == a.revolution
                            and abs(sec.start - a.start) < 1000):
                        dupe = True
                        if sec.crc != 0 and a.crc == 0:
                            self.rev_sectors[i] = a
                        break
                if not dupe:
                    self.rev_sectors.append(a)
            elif isinstance(a, IDAM):
                dupe = False
                for i, idam in enumerate(self.rev_idams):
                    if (idam.revolution == a.revolution
                            and abs(idam.start - a.start) < 1000):
                        dupe = True
                        break
                if not dupe:
                    self.rev_idams.append(a)
        self.iams.sort(key=lambda x: x.start)
        self.rev_sectors.sort(key=lambda x: (x.start, x.revolution))
        self.rev_idams.sort(key=lambda x: (x.start, x.revolution))

    def nr_missing(self) -> int:
        # Always incomplete, so every PLL pass contributes.
        return 1

    def summary_string(self) -> str:
        n_revs = max((s.revolution for s in self.rev_sectors), default=-1) + 1
        positions: List[int] = []
        for s in self.rev_sectors:
            if not any(abs(p - s.start) < 1000 for p in positions):
                positions.append(s.start)
        return '%s (%d sectors, %d revolutions)' % (
            str(self.mode), len(positions), n_revs)


class IBMTrack_MultiRevDef(IBMTrack_FixedDef):
    """Track definition for IBMTrack_MultiRev: only rate and rpm are
    used, the sector layout is whatever is found on the track."""

    def mk_track(  # type: ignore[override]
            self, cyl: int, head: int) -> IBMTrack_MultiRev:
        error.check(self.rate != 0, '%s: rate must be specified'
                    % self.format_name)
        mode = Mode.MFM if self.format_name == 'ibm.mfm.nfd' else Mode.FM
        t = IBMTrack_MultiRev(cyl, head, mode)
        t.time_per_rev = 60 / self.rpm
        t.clock = 5e-4 / self.rate
        return t


class NFDSectorRecord:
    """One sector slot, as written to an NFD_SECT_ID1 entry."""

    def __init__(self, c: int, h: int, r: int, n: int,
                 mfm: bool, ddam: bool,
                 st1: int, st2: int,
                 copies: List[bytes]) -> None:
        self.c, self.h, self.r, self.n = c, h, r, n
        self.mfm, self.ddam = mfm, ddam
        self.st1, self.st2 = st1, st2
        self.copies = copies

    @property
    def byRetry(self) -> int:
        return len(self.copies) - 1

    @property
    def status(self) -> int:
        """byStatus: PC-98 BIOS (INT 1Bh) AH result code, from ST1/ST2.
        0x00 ok, 0x10 DDAM, 0xA0 ID CRC, 0xB0 data CRC, 0xC0 no data,
        0xE0 no ID mark, 0xF0 no data mark."""
        if self.st2 & 0x01:        # MD: Missing Address Mark (Data)
            return 0xF0
        if self.st1 & 0x01:        # MA: Missing Address Mark (ID)
            return 0xE0
        if self.st1 & 0x04:        # ND: No Data
            return 0xC0
        if self.st2 & 0x20:        # DD: Data Error (data field)
            return 0xB0
        if self.st1 & 0x20:        # DE: Data Error (ID field)
            return 0xA0
        if self.st2 & 0x40:        # CM: Control Mark (DDAM)
            return 0x10
        return 0x00


class NFDDiagRecord(NFDSectorRecord):
    """A further occurrence of a C,H,R already present on the track.
    A normal read always finds the first match, so NFD stores these as
    diagnostic-read (READ A TRACK, with ND set) records."""

    DEFAULT_CMD = 0x02  # READ A TRACK

    def __init__(self, *args, cmd: int = DEFAULT_CMD, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.cmd = cmd


class NFDTrackData:
    def __init__(self, sectors: List[NFDSectorRecord],
                 diags: List[NFDDiagRecord]) -> None:
        self.sectors = sectors
        self.diags = diags


def _group_by_position(items, pos_of=lambda x: x.start):
    # Group items at the same position, across revolutions.
    groups: List[list] = []
    for it in sorted(items, key=pos_of):
        pos = pos_of(it)
        for g in groups:
            if abs(pos_of(g[0]) - pos) < 1000:
                g.append(it)
                break
        else:
            groups.append([it])
    for g in groups:
        g.sort(key=lambda x: x.revolution)
    return groups


def analyze_track(track: IBMTrack_MultiRev) -> NFDTrackData:
    sector_slots = _group_by_position(track.rev_sectors)
    sector_positions = [slot[0].start for slot in sector_slots]

    # IDs never followed by a data field in any revolution.
    ma_idams = [idam for idam in track.rev_idams
                if not any(abs(pos - idam.start) < 1000
                           for pos in sector_positions)]
    ma_slots = _group_by_position(ma_idams)

    all_slots = ([('sector', s) for s in sector_slots] +
                 [('ma', s) for s in ma_slots])
    all_slots.sort(key=lambda x: x[1][0].start)

    def chr_key(kind, slot):
        # N is deliberately ignored: a duplicate ID may have a
        # different (often oversized) N.
        idam = slot[0].idam if kind == 'sector' else slot[0]
        return (idam.c, idam.h, idam.r)

    by_chr: Dict[Tuple[int,int,int], List[Tuple[str,list]]] = {}
    for kind, slot in all_slots:
        by_chr.setdefault(chr_key(kind, slot), []).append((kind, slot))

    sectors: List[NFDSectorRecord] = []
    diags: List[NFDDiagRecord] = []

    for kind, slot in all_slots:
        occurrences = by_chr[chr_key(kind, slot)]
        rec = (_build_record(track, slot) if kind == 'sector'
               else _build_ma_record(track, slot))
        if len(occurrences) == 1 or occurrences[0][1] is slot:
            sectors.append(rec)
        else:
            # ND: the ID did not match the one requested.
            diags.append(NFDDiagRecord(
                rec.c, rec.h, rec.r, rec.n, rec.mfm, rec.ddam,
                rec.st1 | 0x04, rec.st2, rec.copies))

    return NFDTrackData(sectors, diags)


def _build_record(track: IBMTrack_MultiRev,
                  slot: List[Sector]) -> NFDSectorRecord:

    # Take status from a CRC-clean revolution if there is one.
    rep = next((s for s in slot if s.idam.crc == 0 and s.dam.crc == 0),
               slot[0])
    st1 = 0x20 if (rep.idam.crc != 0 or rep.dam.crc != 0) else 0
    ddam = rep.dam.mark == Mark.DDAM
    st2 = 0
    if ddam:
        st2 |= 0x40
    if rep.dam.crc != 0:
        st2 |= 0x20

    # Differing revolutions are kept as extra copies (weak bits).
    copies = [s.dam.data for s in slot]
    if all(c == copies[0] for c in copies[1:]):
        copies = [copies[0]]

    return NFDSectorRecord(
        rep.idam.c, rep.idam.h, rep.idam.r, rep.idam.n,
        mfm = (track.mode is Mode.MFM), ddam = ddam,
        st1 = st1, st2 = st2, copies = copies)


def _build_ma_record(track: IBMTrack_MultiRev,
                     slot: List[IDAM]) -> NFDSectorRecord:
    # ID found but no data field: set MA+MD. NFD cannot represent a
    # missing data field, so store a zero-filled placeholder.
    idam = slot[0]
    size = 128 << idam.n
    return NFDSectorRecord(
        idam.c, idam.h, idam.r, idam.n,
        mfm = (track.mode is Mode.MFM), ddam = False,
        st1 = 0x01, st2 = 0x01, copies = [bytes(size)])


# Local variables:
# python-indent: 4
# End:
