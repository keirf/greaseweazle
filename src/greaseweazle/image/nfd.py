# greaseweazle/image/nfd.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# Reading: NFD R0, and NFD R1 at R0-equivalent level.
# Writing: only NFD R1 (gw convert from a raw flux image only).
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from typing import Dict, Tuple, Optional, List

import struct

from greaseweazle import error
from greaseweazle.codec import codec
from greaseweazle.codec.ibm import ibm
from greaseweazle.codec.ibm import ibm_nfd
from greaseweazle.flux import HasFlux
from .image import Image, OptDict

TrackDict = Dict[Tuple[int, int], ibm.IBMTrack_Fixed]

R1_FILE_ID = b'T98FDDIMAGE.R1\0'

NFD_TRKMAX1 = 164  # NFD_FILE_HEAD1.dwTrackHead[] slot count (nfdr1.txt)
NFD_MAX_CYL = 82   # 0-81; format limit (164 slots / 2 heads)

# NFD Rev1d struct layouts (little-endian, unpadded).
HEAD1_FMT = '<15s1s256sLBB10s%dLL12s' % NFD_TRKMAX1  # NFD_FILE_HEAD1
TRACK1_FMT = '<HH12s'                                # NFD_TRACK_ID1
SECT1_FMT = '<12B4s'                                 # NFD_SECT_ID1
DIAG1_FMT = '<10BLB1s'                               # NFD_DIAG_ID1

HEAD1_LEN = struct.calcsize(HEAD1_FMT)
TRACK1_LEN = struct.calcsize(TRACK1_FMT)
SECT1_LEN = struct.calcsize(SECT1_FMT)
DIAG1_LEN = struct.calcsize(DIAG1_FMT)

assert HEAD1_LEN == 0x3c0
assert TRACK1_LEN == SECT1_LEN == DIAG1_LEN == 0x10


class NFD(Image):

    def __init__(self, name: str, _fmt):
        self.to_track: TrackDict = dict()
        self.filename = name
        # Rev1d write path state.
        self.r1d_tracks: Dict[Tuple[int,int],
                              Tuple[ibm_nfd.NFDTrackData, int]] = dict()
        self.max_cyl_seen = -1
        self.max_cyl_used = -1
        # Set if a track was skipped for being beyond NFD_MAX_CYL.
        self.cyl_limit_exceeded = False

    @classmethod
    def from_file(cls, name: str, _fmt, opts: OptDict) -> Image:

        nfd = cls(name, _fmt)
        nfd.apply_r_opts(opts)

        with open(name, 'rb') as f:
            header = struct.unpack('<15sx256sLBB10x', f.read(288))
            file_id, comment_bytes, header_size, write_protect, heads = header
            if file_id == b'T98FDDIMAGE.R1\0':
                f.seek(0)
                nfd._read_r1(f.read())
                return nfd
            if file_id != b'T98FDDIMAGE.R0\0':
                raise error.Fatal('NFD: not a NFD image')
            if heads != 2:
                raise error.Fatal('NFD: heads != 2 not supported')
            comment = comment_bytes.decode('sjis')
            print('NFD: comment:', comment)
            if write_protect != 0:
                print('NFD: disk is write protected')
            for physical_track in range(0, 163):
                secs: List[Tuple[int, int, int, int]] = []
                track = None
                track_mfm = 0
                for _ in range(1, 27):
                    sector_header = struct.unpack('<11B5x', f.read(16))
                    c, h, r, n, mfm, ddam, status, st0, st1, st2, pda = sector_header
                    if c == 0xff:
                        continue
                    if track is None:
                        track_mfm = mfm
                        if mfm != 0:
                            track = ibm.IBMTrack_FixedDef('ibm.mfm')
                            track.rate = 500
                        else:
                            track = ibm.IBMTrack_FixedDef('ibm.fm')
                            track.rate = 250
                        track.rpm = 360
                    else:
                        if track_mfm != mfm:
                            raise error.Fatal(
                                'NFD: mixed FM and MFM tracks not supported')
                    if ddam != 0:
                        raise error.Fatal('NFD: DDAM not supported')
                    if status != 0:
                        raise error.Fatal(
                            f'NFD: Status {status:%02x} not supported')
                    if h not in (0, 1):
                        raise error.Fatal(f'NFD: Invalid head value {h}')
                    if h == 0 and st0 != 0x00:
                        raise error.Fatal(f'NFD: ST0 {st0:%02x} not supported')
                    if h == 1 and st0 != 0x04:
                        raise error.Fatal(f'NFD: ST0 {st0:%02x} not supported')
                    if st1 != 0:
                        raise error.Fatal(f'NFD: ST1 {st1:%02x} not supported')
                    if st2 != 0:
                        raise error.Fatal(f'NFD: ST2 {st2:%02x} not supported')
                    if pda != 0x90:
                        raise error.Fatal(f'NFD: PDA {pda:%02x} not supported')
                    secs.append((c, h, r, n))
                if track is not None:
                    assert track is not None
                    track.secs = len(secs)
                    track.sz = [x[3] for x in secs]
                    track.finalise()
                    t = ibm.IBMTrack_Fixed.from_config(
                        track, physical_track // 2, physical_track % 2,
                        warn_on_oversize=True)
                    for nr, s in enumerate(t.sectors):
                        c, h, r, n = secs[nr]
                        s.crc = s.idam.crc = s.dam.crc = 0
                        s.idam.c, s.idam.h, s.idam.r, s.idam.n = c, h, r, n
                    nfd.to_track[physical_track // 2, physical_track % 2] = t
            f.seek(header_size)
            for _, t in nfd.to_track.items():
                for s in t.sectors:
                    s.dam.data = f.read(128 << s.idam.n)

        return nfd

    def _read_r1(self, dat: bytes) -> None:
        # Read at R0-equivalent level: the first copy of each sector, plus
        # its CRC-error/DDAM status. Weak-bit copies and diagnostic
        # records are skipped.
        (_, _, comment_bytes, header_size, write_protect, heads, _,
         *rest) = struct.unpack(HEAD1_FMT, dat[:HEAD1_LEN])
        dwTrackHead = rest[:NFD_TRKMAX1]
        if heads != 2:
            raise error.Fatal('NFD: heads != 2 not supported')
        comment = comment_bytes.split(b'\0')[0].decode('sjis', 'replace')
        if comment:
            print('NFD: comment:', comment)
        if write_protect != 0:
            print('NFD: disk is write protected')
        # Data is laid out in dwTrackHead[] file-offset order.
        pos = header_size
        nr_copies = nr_diags = nr_status = 0
        for off, trk in sorted((off, trk) for trk, off
                               in enumerate(dwTrackHead) if off):
            nsec, ndiag, _ = struct.unpack(TRACK1_FMT,
                                           dat[off:off+TRACK1_LEN])
            p = off + TRACK1_LEN
            secs = []
            for _ in range(nsec):
                (c, h, r, n, mfm, ddam, status, _st0, st1, st2,
                 retry, pda, _) = struct.unpack(SECT1_FMT,
                                                dat[p:p+SECT1_LEN])
                p += SECT1_LEN
                size = 128 << n
                secs.append((c, h, r, n, mfm, ddam, st1, st2, pda,
                             dat[pos:pos+size]))
                pos += size * (retry + 1)
                nr_copies += retry
                if status != 0:
                    nr_status += 1
            for _ in range(ndiag):
                fields = struct.unpack(DIAG1_FMT, dat[p:p+DIAG1_LEN])
                p += DIAG1_LEN
                retry, datalen = fields[9], fields[10]
                pos += datalen * (retry + 1)
                nr_diags += 1
            if secs:
                self.to_track[trk//2, trk%2] = _r1_track(trk, secs)
        if nr_copies or nr_diags or nr_status:
            print('NFD: read at R0-equivalent level: %d sector(s) with '
                  'error/DDAM status; skipped %d weak-bit copies, %d '
                  'diagnostic records' % (nr_status, nr_copies, nr_diags))

    def get_track(self, cyl: int, side: int) -> Optional[ibm.IBMTrack_Fixed]:
        if (cyl, side) not in self.to_track:
            return None
        return self.to_track[cyl, side]

    def emit_track(self, cyl: int, side: int, track: HasFlux) -> None:

        if cyl >= NFD_MAX_CYL:
            # dwTrackHead[] cannot address this cylinder.
            self.cyl_limit_exceeded = True
            if cyl > self.max_cyl_seen:
                self.max_cyl_seen = cyl
            print('NFD: WARNING: C%d.%d is beyond the Rev1d cylinder '
                  'limit (0-%d); track skipped (data remains in the '
                  'source image)' % (cyl, side, NFD_MAX_CYL - 1))
            return

        if not isinstance(track, ibm_nfd.IBMTrack_MultiRev):
            raise error.Fatal(
                'NFD: output is only supported by "gw convert" from a raw '
                'flux image with an IBM FM/MFM format (eg. --format '
                'pc98.2hd); got %s' % type(track).__name__)

        data = ibm_nfd.analyze_track(track)
        if not data.sectors and not data.diags:
            return
        if cyl > self.max_cyl_used:
            self.max_cyl_used = cyl
        self.r1d_tracks[cyl, side] = (
            data, _pda_for(track.mode, track.clock, track.time_per_rev))

    def get_image(self) -> bytes:

        track_blocks = bytearray()
        data_blocks = bytearray()
        dwTrackHead = [0] * NFD_TRKMAX1

        for (cyl, side), (data, pda) in sorted(self.r1d_tracks.items()):
            trk = cyl * 2 + side
            dwTrackHead[trk] = HEAD1_LEN + len(track_blocks)

            track_blocks += struct.pack(
                TRACK1_FMT, len(data.sectors), len(data.diags), bytes(12))

            for s in data.sectors:
                # ST0 has only the head-select bit (drive bits unknown).
                track_blocks += struct.pack(
                    SECT1_FMT,
                    s.c, s.h, s.r, s.n,
                    int(s.mfm), int(s.ddam),
                    s.status, s.h << 2, s.st1, s.st2,
                    s.byRetry, pda,
                    bytes(4))
                for copy in s.copies:
                    data_blocks += copy

            for d in data.diags:
                track_blocks += struct.pack(
                    DIAG1_FMT,
                    d.cmd, d.c, d.h, d.r, d.n,
                    d.status, d.h << 2, d.st1, d.st2, d.byRetry,
                    len(d.copies[0]), pda,
                    bytes(1))
                for copy in d.copies:
                    data_blocks += copy

        headsize = HEAD1_LEN + len(track_blocks)

        # Real NFDMAKE dumps leave the comment blank.
        comment = b''
        print('NFD: cylinders used: 0-%d' % max(self.max_cyl_used, 0))

        header = struct.pack(
            HEAD1_FMT,
            R1_FILE_ID, b'\0', comment, headsize,
            # flProtect: 0 (writable), as in real NFDMAKE dumps
            0,
            2,  # byHead: 2-head PC-98 drives only
            bytes(10),
            *dwTrackHead,
            0,  # dwAddInfo: reserved (must be 0 per nfdr1.txt)
            bytes(12))

        return header + bytes(track_blocks) + bytes(data_blocks)


def _pda_for(mode: ibm.Mode, clock: float, time_per_rev: float) -> int:
    # NFD media-type byte, from the track's channel rate and rpm
    # (so FM counts at twice its data rate):
    #   0x10 = 2DD (250kbps), 0x90 = 2HD (500kbps, 360rpm),
    #   0x30 = 500kbps at 300rpm (unconfirmed on hardware)
    rate = 5e-4 / clock     # kbps
    if mode is ibm.Mode.FM:
        rate *= 2
    rpm = 60 / time_per_rev
    if abs(rate - 250) < 5:
        return 0x10
    if abs(rate - 500) < 5 and abs(rpm - 360) < 5:
        return 0x90
    if abs(rate - 500) < 5 and abs(rpm - 300) < 5:
        return 0x30
    raise error.Fatal('NFD: no NFD media type for %g kbit/s at %g rpm'
                      % (rate, rpm))


def _r1_track(trk: int, secs) -> ibm.IBMTrack_Fixed:
    mfm = secs[0][4]
    if any(x[4] != mfm for x in secs):
        raise error.Fatal('NFD: mixed FM and MFM tracks not supported')
    pda = secs[0][8]
    # Inverse of _pda_for(). 0x10 does not say 300 or 360rpm: assume 360.
    rates = { 0x10: (250, 360), 0x30: (500, 300), 0x90: (500, 360) }
    if pda not in rates:
        raise error.Fatal(f'NFD: PDA {pda:02x} not supported')
    rate, rpm = rates[pda]
    if mfm:
        track = ibm.IBMTrack_FixedDef('ibm.mfm')
        track.rate = rate
    else:
        track = ibm.IBMTrack_FixedDef('ibm.fm')
        track.rate = rate // 2
    track.rpm = rpm
    track.secs = len(secs)
    track.sz = [x[3] for x in secs]
    track.finalise()
    t = ibm.IBMTrack_Fixed.from_config(track, trk // 2, trk % 2,
                                       warn_on_oversize=True)
    for s, (c, h, r, n, _, ddam, st1, st2, _, data) in zip(t.sectors, secs):
        s.idam.c, s.idam.h, s.idam.r, s.idam.n = c, h, r, n
        # DE without DD: ID CRC error. DD, MA or MD: bad data field.
        s.idam.crc = 0xffff if (st1 & 0x20) and not (st2 & 0x20) else 0
        s.dam.crc = 0xffff if (st2 & 0x21) or (st1 & 0x01) else 0
        s.crc = s.idam.crc | s.dam.crc
        if ddam:
            s.dam.mark = ibm.Mark.DDAM
        s.dam.data = data
    return t


def multirev_diskdef(disk: codec.DiskDef) -> codec.DiskDef:
    # Decode IBM FM/MFM tracks with IBMTrack_MultiRev, and extend the
    # disk to NFD_MAX_CYL cylinders.
    multirev: Dict[int, codec.TrackDef] = dict()
    for key, td in list(disk.track_map.items()):
        if (isinstance(td, ibm.IBMTrack_FixedDef)
                and td.format_name in ('ibm.mfm', 'ibm.fm')):
            if id(td) not in multirev:
                m = ibm_nfd.IBMTrack_MultiRevDef(td.format_name + '.nfd')
                m.rate, m.rpm = td.rate, td.rpm
                m.finalise()
                multirev[id(td)] = m
            disk.track_map[key] = multirev[id(td)]
    assert disk.cyls is not None and disk.heads is not None # mypy
    for c in range(disk.cyls, NFD_MAX_CYL):
        for h in range(disk.heads):
            last = disk.track_map.get((disk.cyls - 1, h))
            if last is not None:
                disk.track_map[c, h] = last
    disk.cyls = max(disk.cyls, NFD_MAX_CYL)
    disk.finalise()
    return disk

# Local variables:
# python-indent: 4
# End:
