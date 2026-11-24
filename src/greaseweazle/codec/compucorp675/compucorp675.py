# greaseweazle/codec/compucorp675/compucorp675.py
#
# Compucorp 675 / Metric 85 hard-sectored 5.25" MFM disks.
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from typing import Dict, List, Optional

import itertools as it
from collections import Counter
from bitarray import bitarray
import crcmod.predefined

from greaseweazle import error
from greaseweazle.codec import codec
from greaseweazle.codec.ibm.ibm import decode, encode, mfm_encode
from greaseweazle.track import MasterTrack, PLL, PLLTrack
from greaseweazle.flux import HasFlux

# Physical format
# ---------------
# 5.25" DSDD 96tpi, 80 cylinders, 300 RPM, 16 hard sectors (+ index hole
# between two sector holes), MFM at 250kbps, 256-byte sectors (640kB total).
# All bytes are recorded LSB first.
#
# Each hard sector holds (byte values as seen by the CPU, i.e. LSB-first):
#   ~50: 00 preamble
#     1: A5 sync
#     5: header: cylinder, sector, 3 'magic' bytes (B4 C0 CC observed)
#     2: CRC over the 5 header bytes
#   ~40: 00 gap/preamble (the original controller leaves a write splice here)
#     1: A5 sync
#   256: data
#     2: CRC over the 256 data bytes
#    NN: 00 postamble
# CRCs are CRC-16/ARC (poly 0x8005 reflected, init 0), stored little endian.
#
# The sector numbering is skewed: the first hard sector after the index holds
# sector (first + cskew*cyl + hskew*head) % 16, with first=12, cskew=11 (-5)
# and hskew=14 (-2), verified on all 160 tracks of a full 80-track 2-sided disk.
#
# The filesystem numbers blocks as (cyl*2 + head)*16 + sector, which matches
# the ordering of a Greaseweazle .img file for an 80-cylinder 2-sided disk.

default_revs = 2

bad_sector = b'-=[BAD SECTOR]=-'

crc16 = crcmod.predefined.mkPredefinedCrcFun('crc-16')  # CRC-16/ARC

# Bit-reverse table: bytes are recorded on disk LSB first.
_rev = bytes(int(f'{x:08b}'[::-1], 2) for x in range(256))

def _rev_bytes(dat: bytes) -> bytes:
    return dat.translate(_rev)

def _enc(dat: bytes) -> bytes:
    """Data bytes (LSB-first on disk) -> MSB-first byte stream for encode()."""
    return encode(_rev_bytes(dat))

def _dec(bits: bitarray) -> bytes:
    return _rev_bytes(decode(bits.tobytes()))

# Sync: tail of the zero preamble followed by A5 (A5 reads the same in
# either bit order). Matching the preceding zeros avoids false syncs.
_sync = bitarray(endian='big')
_sync.frombytes(mfm_encode(encode(b'\x00\x00\xa5')))
_sync = _sync[2:]   # first clock bit depends on what precedes the preamble
_sync_len = len(_sync)

# Distance from header sync to data sync, in bitcells (nominally ~767).
_data_sync_min, _data_sync_max = 30*16, 70*16

# Header/data start positions within a written hard sector (in bytes).
_hdr_pos, _data_pos = 52, 100

# PLLs tried, in order, if the caller doesn't specify one. Hard-sectored
# Compucorp disks read on a drive other than the original are often slightly
# off-track; a stiff, slow PLL copes best with the resulting peak jitter.
_plls = [PLL('period=1:phase=15'), PLL('period=1:phase=10'),
         PLL('period=1:phase=20'), PLL('period=1:phase=30'),
         PLL('period=1:phase=5'), PLL('period=2:phase=30'),
         PLL('period=5:phase=60')]


class Compucorp675(codec.Codec):

    time_per_rev = 0.2

    verify_revs: float = default_revs

    def __init__(self, cyl: int, head: int, config):
        self.clock = 2e-6
        self.cyl, self.head = cyl, head
        self.config = config
        self.sector: List[Optional[bytes]] = [None] * self.nsec

    @property
    def nsec(self) -> int:
        return 16

    def summary_string(self) -> str:
        nsec, nbad = self.nsec, self.nr_missing()
        return "Compucorp 675 (%d/%d sectors)" % (nsec - nbad, nsec)

    def has_sec(self, sec_id: int) -> bool:
        return self.sector[sec_id] is not None

    def nr_missing(self) -> int:
        return len([sec for sec in self.sector if sec is None])

    def get_img_track(self) -> bytearray:
        tdat = bytearray()
        for sec in self.sector:
            tdat += sec if sec is not None else bad_sector * 16
        return tdat

    def set_img_track(self, tdat: bytes) -> int:
        totsize = self.nsec * 256
        if len(tdat) < totsize:
            tdat += bytes(totsize - len(tdat))
        for sec in range(self.nsec):
            self.sector[sec] = tdat[sec*256:(sec+1)*256]
        return totsize

    def decode_flux(self, track: HasFlux, pll: Optional[PLL]=None) -> None:
        flux = track.flux()
        if flux.time_per_rev < self.time_per_rev / 2:
            flux.identify_hard_sectors()
        flux.cue_at_index()

        # Data fields with a good header but bad data CRC, kept for repair.
        candidates: Dict[int, List[bytes]] = dict()
        bad_cyl: Optional[int] = None

        for p in [pll] if pll is not None else _plls:
            if self.nr_missing() == 0:
                break
            # Decode all revolutions as one stream: sector IDs come from the
            # headers, so hard-sector boundaries are not needed for decoding.
            raw = PLLTrack(time_per_rev = self.time_per_rev,
                           clock = self.clock, data = flux, pll = p)
            bits, _ = raw.get_all_data()
            syncs = list(bits.search(_sync))
            for i, s in enumerate(syncs):
                s += _sync_len
                hdr = _dec(bits[s:s+7*16])
                if len(hdr) != 7 or crc16(hdr[:5]) != (hdr[5] | hdr[6]<<8):
                    continue
                cyl, sec_id = hdr[0], hdr[1]
                if cyl != self.cyl or sec_id >= self.nsec:
                    bad_cyl = cyl
                    continue
                if self.has_sec(sec_id):
                    continue
                # The data sync must follow the header sync closely.
                d = [x for x in syncs[i+1:i+3]
                     if _data_sync_min < x + _sync_len - s < _data_sync_max]
                if not d:
                    continue # header only: sector was never written
                s = d[0] + _sync_len
                dat = _dec(bits[s:s+258*16])
                if len(dat) != 258:
                    continue
                if crc16(dat[:256]) == (dat[256] | dat[257]<<8):
                    self.sector[sec_id] = dat[:256]
                else:
                    candidates.setdefault(sec_id, []).append(dat)

        # Repair: off-track reads suffer bit slips at different places in
        # each read. Try byte-wise majority, then splicing pairs of reads.
        for sec_id, cands in candidates.items():
            if not self.has_sec(sec_id):
                self.sector[sec_id] = self._repair(cands)

        if bad_cyl is not None and self.nr_missing() == self.nsec:
            print('T%d.%d: Compucorp 675: Found only cylinder %d headers'
                  % (self.cyl, self.head, bad_cyl))

    @staticmethod
    def _repair(cands: List[bytes]) -> Optional[bytes]:
        def ok(dat):
            return crc16(dat[:256]) == (dat[256] | dat[257]<<8)
        vote = bytes(Counter(c[i] for c in cands).most_common(1)[0][0]
                     for i in range(258))
        if ok(vote):
            return vote[:256]
        # Splice only where two reads start to disagree, so this stays cheap.
        uniq = list(dict.fromkeys(cands))[:32]
        for x, y in it.permutations(uniq, 2):
            for k in range(1, 258):
                if x[k] != y[k] and x[k-1] == y[k-1]:
                    dat = x[:k] + y[k:]
                    if ok(dat):
                        return dat[:256]
        return None

    def sector_at_slot(self, slot: int) -> int:
        c = self.config
        return (c.first + c.cskew*self.cyl + c.hskew*self.head + slot) % 16

    def master_track(self) -> MasterTrack:

        # Hard-sector length in bytes (390).
        slen = int(self.time_per_rev / self.clock / self.nsec / 16)

        t = bytes()
        for slot in range(self.nsec):
            sec_id = self.sector_at_slot(slot)
            data = self.sector[sec_id]
            if data is None:
                data = bad_sector * 16
            hdr = bytes([self.cyl, sec_id]) + self.config.magic
            hdr += crc16(hdr).to_bytes(2, 'little')
            s = _enc(bytes(_hdr_pos) + b'\xa5' + hdr)
            s += _enc(bytes(_data_pos - len(s)//2) + b'\xa5' + data
                      + crc16(data).to_bytes(2, 'little'))
            s += encode(bytes(slen - len(s)//2))
            t += s

        t = mfm_encode(t)

        track = MasterTrack(bits = t, time_per_rev = self.time_per_rev,
                            hardsector_bits = [slen*16] * self.nsec)
        track.verify = self
        return track

    def verify_track(self, flux):
        readback_track = self.__class__(self.cyl, self.head, self.config)
        readback_track.decode_flux(flux)
        return (readback_track.nr_missing() == 0
                and self.sector == readback_track.sector)


class Compucorp675Def(codec.TrackDef):

    default_revs = default_revs

    def __init__(self, format_name: str):
        self.first = 12
        self.cskew = 11
        self.hskew = 14
        self.magic = b'\xb4\xc0\xcc'
        self.finalised = False

    def add_param(self, key: str, val) -> None:
        if key in ('first', 'cskew', 'hskew'):
            n = int(val)
            error.check(0 <= n < 16, '%s out of range' % key)
            setattr(self, key, n)
        elif key == 'magic':
            error.check(len(val) == 6, 'magic must be 3 hex bytes')
            self.magic = bytes.fromhex(val)
        else:
            raise error.Fatal('unrecognised track option %s' % key)

    def finalise(self) -> None:
        self.finalised = True

    def mk_track(self, cyl: int, head: int) -> Compucorp675:
        return Compucorp675(cyl, head, self)


# Local variables:
# python-indent: 4
# End:
