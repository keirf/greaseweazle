# greaseweazle/image/edsk.py
#
# Some of the code here is heavily inspired by Simon Owen's SAMdisk:
# https://simonowen.com/samdisk/
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
# 
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from typing import Dict, Tuple, Optional, List, Union

import binascii, math, struct
import itertools as it
from bitarray import bitarray

from greaseweazle import __version__
from greaseweazle import error
from greaseweazle.flux import Flux
from greaseweazle.codec.ibm import ibm
from greaseweazle.track import MasterTrack, PLLTrack
from .image import Image

class EDSKRate:
    Unknown          = 0
    DoubleDensity    = 1
    HighDensity      = 2
    ExtendedDensity  = 3

class SR1:
    SUCCESS                   = 0x00
    CANNOT_FIND_ID_ADDRESS    = 0x01
    WRITE_PROTECT_DETECTED    = 0x02
    CANNOT_FIND_SECTOR_ID     = 0x04
    RESERVED1                 = 0x08
    OVERRUN                   = 0x10
    CRC_ERROR                 = 0x20
    RESERVED2                 = 0x40
    END_OF_CYLINDER           = 0x80

class SR2:
    SUCCESS                   = 0x00
    MISSING_ADDRESS_MARK      = 0x01
    BAD_CYLINDER              = 0x02
    SCAN_COMMAND_FAILED       = 0x04
    SCAN_COMMAND_EQUAL        = 0x08
    WRONG_CYLINDER_DETECTED   = 0x10
    CRC_ERROR_IN_SECTOR_DATA  = 0x20
    SECTOR_WITH_DELETED_DATA  = 0x40
    RESERVED                  = 0x80

class SectorErrors:
    def __init__(self, sr1: int, sr2: int):
        self.id_crc_error = (sr1 & SR1.CRC_ERROR) != 0
        self.data_not_found = (sr2 & SR2.MISSING_ADDRESS_MARK) != 0
        self.data_crc_error = (sr2 & SR2.CRC_ERROR_IN_SECTOR_DATA) != 0
        self.deleted_dam = (sr2 & SR2.SECTOR_WITH_DELETED_DATA) != 0
        if self.data_crc_error:
            # uPD765 sets both id and data flags for data CRC errors
            self.id_crc_error = False
        if (# normal data
            (sr1 == SR1.SUCCESS and sr2 == SR2.SUCCESS) or
            # deleted data
            (sr1 == SR1.SUCCESS and sr2 == SR2.SECTOR_WITH_DELETED_DATA) or
            # end of track
            (sr1 == SR1.END_OF_CYLINDER and sr2 == SR2.SUCCESS) or
            # id crc error
            (sr1 == SR1.CRC_ERROR and sr2 == SR2.SUCCESS) or
            # normal data crc error
            (sr1 == SR1.CRC_ERROR and sr2 == SR2.CRC_ERROR_IN_SECTOR_DATA) or
            # deleted data crc error
            (sr1 == SR1.CRC_ERROR and sr2 == (SR2.CRC_ERROR_IN_SECTOR_DATA |
                                              SR2.SECTOR_WITH_DELETED_DATA)) or
            # data field missing (some FDCs set AM in ST1)
            (sr1 == SR1.CANNOT_FIND_ID_ADDRESS
             and sr2 == SR2.MISSING_ADDRESS_MARK) or
            # data field missing (some FDCs don't)
            (sr1 == SR1.SUCCESS and sr2 == SR2.MISSING_ADDRESS_MARK) or
            # CHRN mismatch
            (sr1 == SR1.CANNOT_FIND_SECTOR_ID and sr2 == SR2.SUCCESS) or
            # CHRN mismatch, including wrong cylinder
            (sr1 == SR1.CANNOT_FIND_SECTOR_ID
             and sr2 == SR2.WRONG_CYLINDER_DETECTED)):
            pass
        else:
            print('Unusual status flags (ST1=%02X ST2=%02X)' % (sr1, sr2))
            
class EDSKTrack:

    gap_presync = 12
    gap_4a = 80 # Post-Index
    gap_1  = 50 # Post-IAM
    gap_2  = 22 # Post-IDAM

    gapbyte = 0x4e
    
    verify_len: int
    verify_revs: float = 1

    def __init__(self, rate = 0) -> None:
        self.time_per_rev = 0.2
        if rate == EDSKRate.HighDensity:
            self.clock = 1e-6
        elif rate == EDSKRate.ExtendedDensity:
            self.clock = 5e-7
        else: # Double Density, or unknown
            self.clock = 2e-6
        self.bits = bitarray(endian='big')
        self.weak: List[Tuple[int,int]] = []
        self.bytes = bytearray()

    def master_track(self) -> MasterTrack:
        track = MasterTrack(
            bits = self.bits,
            time_per_rev = self.time_per_rev,
            weak = self.weak)
        track.verify = self
        return track

    def _find_sync(self, bits: bitarray, sync, start) -> Optional[int]:
        for offs in bits.search(sync):
            if offs >= start:
                return offs
        return None
    
    def verify_track(self, flux: Flux) -> bool:
        flux.cue_at_index()
        raw = PLLTrack(time_per_rev = self.time_per_rev,
                       clock = self.time_per_rev / len(self.bits),
                       data = flux)
        bits, _ = raw.get_all_data()
        weak_iter = it.chain(self.weak, [(self.verify_len+1,1)])
        weak = next(weak_iter)

        # Start checking from the IAM sync
        dump_start = self._find_sync(bits, ibm.mfm_iam_sync, 0)
        self_start = self._find_sync(self.bits, ibm.mfm_iam_sync, 0)
        assert self_start is not None

        # Include the IAM pre-sync header
        if dump_start is None:
            return False
        dump_start -= self.gap_presync * 16
        self_start -= self.gap_presync * 16

        while self_start is not None and dump_start is not None:

            # Find the weak areas immediately before and after the current
            # region to be checked.
            s,n = None,None
            while self_start > weak[0]:
                s,n = weak
                weak = next(weak_iter)

            # If there is a weak area preceding us, move the start point to
            # immediately follow the weak area.
            if s is not None:
                assert n is not None # mypy
                delta = self_start - (s + n + 16)
                self_start -= delta
                dump_start -= delta

            # Truncate the region at the next weak area, or the last sector.
            self_end = max(self_start, min(weak[0], self.verify_len+1))
            dump_end = dump_start + self_end - self_start

            # Extract the corresponding areas from the pristine track and
            # from the dump, and check that they match.
            if bits[dump_start:dump_end] != self.bits[self_start:self_end]:
                return False

            # Find the next A1A1A1 sync pattern
            dump_start = self._find_sync(bits, ibm.mfm_sync, dump_end)
            self_start = self._find_sync(self.bits, ibm.mfm_sync, self_end)

        # Did we verify all regions in the pristine track?
        return self_start is None

class EDSK(Image):

    def __init__(self, name: str, _fmt) -> None:
        self.to_track: Dict[Tuple[int,int],
                            Union[ibm.IBMTrack,EDSKTrack]] = dict()
        self.filename = name

    # Find all weak ranges in the given sector data copies.
    @staticmethod
    def find_weak_ranges(dat: bytes, size: int) -> List[Tuple[int,int]]:
        orig = dat[:size]
        s, w = size, []
        # Find first mismatching byte across all copies
        for i in range(1, len(dat)//size):
            diff = [x^y for x, y in zip(orig, dat[size*i:size*(i+1)])]
            weak = [idx for idx, val in enumerate(diff) if val != 0]
            if weak:
                s = min(s, weak[0])
        # Look for runs of filler
        i = s
        while i < size:
            j, x = i, orig[i]
            while j < size and orig[j] == x:
                j += 1
            if j-i >= 16:
                w.append((s,i-s))
                s = j
            i = j
        # Append final weak area if any.
        if s < size:
            w.append((s,size-s))
        return w

    @staticmethod
    def _build_8k_track(sectors: List) -> Optional[EDSKTrack]:
        if len(sectors) != 1:
            return None
        c,h,r,n,errs,data = sectors[0]
        if n != 6:
            return None
        if errs.id_crc_error or errs.data_not_found or not errs.data_crc_error:
            return None
        # Magic longtrack value is for Coin-Op Hits. Taken from SAMdisk.
        if len(data) > 6307:
            data = data[:6307]
        track = EDSKTrack()
        t = track.bytes
        # Post-index gap
        t += ibm.encode(bytes([track.gapbyte] * 16))
        # IAM
        t += ibm.encode(bytes(track.gap_presync))
        t += ibm.mfm_iam_sync_bytes
        t += ibm.encode(bytes([ibm.Mark.IAM]))
        t += ibm.encode(bytes([track.gapbyte] * 16))
        # IDAM
        t += ibm.encode(bytes(track.gap_presync))
        t += ibm.mfm_sync_bytes
        am = bytes([0xa1, 0xa1, 0xa1, ibm.Mark.IDAM, c, h, r, n])
        crc = ibm.crc16.new(am).crcValue
        am += struct.pack('>H', crc)
        t += ibm.encode(am[3:])
        t += ibm.encode(bytes([track.gapbyte] * track.gap_2))
        # DAM
        t += ibm.encode(bytes(track.gap_presync))
        t += ibm.mfm_sync_bytes
        dmark = (ibm.Mark.DDAM if errs.deleted_dam
                 else ibm.Mark.DAM)
        am = bytes([0xa1, 0xa1, 0xa1, dmark]) + data
        t += ibm.encode(am[3:])
        return track

    @staticmethod
    def _build_kbi19_track(sectors: List) -> Optional[EDSKTrack]:
        ids = [0,1,4,7,10,13,16,2,5,8,11,14,17,3,6,9,12,15,18]
        if len(sectors) != len(ids):
            return None
        for s,id in zip(sectors,ids):
            c,h,r,n,_,_ = s
            if r != id or n != 2:
                return None
        def addcrc(t,n):
            crc = ibm.crc16.new(ibm.decode(t[-n*2:])).crcValue
            t += ibm.encode(struct.pack('>H', crc))
        track = EDSKTrack()
        t = track.bytes
        # Post-index gap
        t += ibm.encode(bytes([track.gapbyte] * 64))
        # IAM
        t += ibm.encode(bytes(track.gap_presync))
        t += ibm.mfm_iam_sync_bytes
        t += ibm.encode(bytes([ibm.Mark.IAM]))
        t += ibm.encode(bytes([track.gapbyte] * 50))
        for idx, s in enumerate(sectors):
            c,h,r,n,errs,data = s
            # IDAM
            t += ibm.encode(bytes(track.gap_presync))
            t += ibm.mfm_sync_bytes
            t += ibm.encode(bytes([ibm.Mark.IDAM, c, h, r, n]))
            addcrc(t, 8)
            if r == 0:
                t += ibm.encode(bytes([track.gapbyte] * 17))
                t += ibm.encode(b' KBI ')
            else:
                t += ibm.encode(bytes([track.gapbyte] * 8))
                t += ibm.encode(b' KBI ')
                t += ibm.encode(bytes([track.gapbyte] * 9))
            # DAM
            t += ibm.encode(bytes(track.gap_presync))
            t += ibm.mfm_sync_bytes
            dmark = (ibm.Mark.DDAM if errs.deleted_dam
                     else ibm.Mark.DAM)
            t += ibm.encode(bytes([dmark]))
            if idx%3 != 0:
                t += ibm.encode(data[:61])
            elif r == 0:
                t += ibm.encode(data[:512])
                addcrc(t,516)
            else:
                t += ibm.encode(data[0:0x10e])
                addcrc(t,516)
                t += ibm.encode(data[0x110:0x187])
                addcrc(t,516)
                t += ibm.encode(data[0x189:0x200])
                addcrc(t,516)
                t += ibm.encode(bytes([track.gapbyte] * 80))
        return track

    def from_bytes(self, dat: bytes) -> None:

        sig, creator, ncyls, nsides, track_sz = struct.unpack(
            '<34s14s2BH', dat[:52])
        if sig[:8] == b'MV - CPC':
            extended = False
        elif sig[:16] == b'EXTENDED CPC DSK':
            extended = True
        else:
            raise error.Fatal('Unrecognised CPC DSK file: bad signature')

        if extended:
            track_sizes = list(dat[52:52+ncyls*nsides])
            track_sizes = list(map(lambda x: x*256, track_sizes))
        else:
            track_sizes = [track_sz] * (ncyls * nsides)

        o = 256 # skip disk header and track-size table
        for track_size in track_sizes:
            if track_size == 0:
                continue
            x = struct.unpack('<12s4x8B', dat[o:o+24])
            sig, cyl, head, rate, mode, sec_sz, nsecs, gap_3, filler = x
            error.check(sig == b'Track-Info\r\n',
                        'EDSK: Missing track header')
            error.check((cyl, head) not in self.to_track,
                        'EDSK: Track specified twice')
            bad_crc_clip_data = False
            while True:
                track = EDSKTrack(rate)
                t = track.bytes
                # Post-index gap
                t += ibm.encode(bytes([track.gapbyte] * track.gap_4a))
                # IAM
                t += ibm.encode(bytes(track.gap_presync))
                t += ibm.mfm_iam_sync_bytes
                t += ibm.encode(bytes([ibm.Mark.IAM]))
                t += ibm.encode(bytes([track.gapbyte] * track.gap_1))
                sh = dat[o+24:o+24+8*nsecs]
                data_pos = o + 256 # skip track header and sector-info table
                clippable, ngap3, sectors, idam_included = 0, 0, [], False
                while sh:
                    c, h, r, n, stat1, stat2, data_size = struct.unpack(
                        '<6BH', sh[:8])
                    sh = sh[8:]
                    native_size = ibm.sec_sz(n)
                    weak = []
                    errs = SectorErrors(stat1, stat2)
                    num_copies = 0 if errs.data_not_found else 1
                    if not extended:
                        data_size = ibm.sec_sz(sec_sz)
                    sec_data = dat[data_pos:data_pos+data_size]
                    data_pos += data_size
                    if (extended
                        and data_size > native_size
                        and errs.data_crc_error
                        and (data_size % native_size == 0
                             or data_size == 49152)):
                        num_copies = (3 if data_size == 49152
                                      else data_size // native_size)
                        data_size //= num_copies
                        weak = EDSK.find_weak_ranges(sec_data, data_size)
                        sec_data = sec_data[:data_size]
                    sectors.append((c,h,r,n,errs,sec_data))
                    # IDAM
                    if not idam_included:
                        t += ibm.encode(bytes(track.gap_presync))
                        t += ibm.mfm_sync_bytes
                        am = bytes([0xa1, 0xa1, 0xa1, ibm.Mark.IDAM,
                                    c, h, r, n])
                        crc = ibm.crc16.new(am).crcValue
                        if errs.id_crc_error:
                            crc ^= 0x5555
                        am += struct.pack('>H', crc)
                        t += ibm.encode(am[3:])
                        t += ibm.encode(bytes([track.gapbyte] * track.gap_2))
                    # DAM
                    gap_included, idam_included = False, False
                    if errs.id_crc_error or errs.data_not_found:
                        continue
                    t += ibm.encode(bytes(track.gap_presync))
                    t += ibm.mfm_sync_bytes
                    track.weak += [((s+len(t)//2+1)*16, n*16) for s,n in weak]
                    dmark = (ibm.Mark.DDAM if errs.deleted_dam
                             else ibm.Mark.DAM)
                    if errs.data_crc_error:
                        if sh:
                            # Look for next IDAM
                            idam = bytes([0]*12 + [0xa1]*3
                                         + [ibm.Mark.IDAM])
                            idx = sec_data.find(idam)
                        else:
                            # Last sector: Look for GAP3
                            idx = sec_data.find(bytes([track.gapbyte]*8))
                        if idx > 0:
                            # 2 + gap_3 = CRC + GAP3 (because gap_included)
                            clippable += data_size - idx + 2 + gap_3
                            if bad_crc_clip_data:
                                data_size = idx
                                sec_data = sec_data[:data_size]
                                gap_included = True
                    elif data_size < native_size:
                        # Pad short data
                        sec_data += bytes(native_size - data_size)
                    elif data_size > native_size:
                        # Clip long data if it includes pre-sync 00 bytes
                        if (sec_data[-13] != 0
                            and all([v==0 for v in sec_data[-12:]])):
                            # Includes next pre-sync: Clip it.
                            sec_data = sec_data[:-12]
                        if sh:
                            # Look for next IDAM
                            idam = bytes([0]*12 + [0xa1]*3 + [ibm.Mark.IDAM]
                                         + list(sh[:4]))
                            idx = sec_data.find(idam)
                            if idx > native_size:
                                # Sector data includes next IDAM. Output it
                                # here and skip it on next iteration.
                                t += ibm.encode(bytes([dmark]))
                                t += ibm.encode(sec_data[:idx+12])
                                t += ibm.mfm_sync_bytes
                                t += ibm.encode(sec_data[idx+12+3:])
                                idam_included = True
                                continue
                        # Long data includes CRC and GAP
                        gap_included = True
                    if gap_included:
                        t += ibm.encode(bytes([dmark]))
                        t += ibm.encode(sec_data)
                        continue
                    am = bytes([0xa1, 0xa1, 0xa1, dmark]) + sec_data
                    crc = ibm.crc16.new(am).crcValue
                    if errs.data_crc_error:
                        crc ^= 0x5555
                    am += struct.pack('>H', crc)
                    t += ibm.encode(am[3:])
                    if sh:
                        # GAP3 for all but last sector
                        t += ibm.encode(bytes([track.gapbyte] * gap_3))
                        ngap3 += 1

                # Special track handlers
                special_track = EDSK._build_8k_track(sectors)
                if special_track is None:
                    special_track = EDSK._build_kbi19_track(sectors)
                if special_track is not None:
                    track = special_track
                    break

                # The track may be too long to fit: Check for overhang.
                tracklen = int((track.time_per_rev / track.clock) / 16)
                overhang = int(len(t)//2 - tracklen*0.99)
                if overhang <= 0:
                    break

                # Some EDSK tracks with Bad CRC contain a raw dump following
                # the DAM. This can usually be clipped.
                if clippable and not bad_crc_clip_data:
                    bad_crc_clip_data = True
                    continue

                # Some EDSK images have bogus GAP3 values. Shrink it if
                # necessary.
                new_gap_3 = -1
                if ngap3 != 0:
                    new_gap_3 = gap_3 - math.ceil(overhang / ngap3)
                error.check(new_gap_3 >= 0,
                            'EDSK: Track %d.%d is too long '
                            '(%d bits @ GAP3=%d; %d bits @ GAP3=0)'
                            % (cyl, head, len(t)*8, gap_3,
                               (len(t)//2-gap_3*ngap3)*16))
                #print('EDSK: GAP3 reduced (%d -> %d)' % (gap_3, new_gap_3))
                gap_3 = new_gap_3

            # Pre-index gap
            track.verify_len = len(track.bytes)*8
            tracklen = int((track.time_per_rev / track.clock) / 16)
            gap = max(40, tracklen - len(t)//2)
            track.bytes += ibm.encode(bytes([track.gapbyte] * gap))

            # Add the clock buts
            track.bits = bitarray(endian='big')
            track.bits.frombytes(ibm.mfm_encode(track.bytes))

            # Register the track
            self.to_track[cyl,head] = track
            o += track_size


    def get_track(self, cyl: int, side: int) -> Optional[MasterTrack]:
        if (cyl,side) not in self.to_track:
            return None
        return self.to_track[cyl,side].master_track()


    def emit_track(self, cyl: int, side: int, track) -> None:
        if isinstance(track, ibm.IBMTrack_Scan):
            track = track.track
        error.check(isinstance(track, ibm.IBMTrack),
                    'EDSK: Cannot create T%d.%d: Not IBM.FM nor IBM.MFM'
                    % (cyl, side))
        if not isinstance(track, ibm.IBMTrack_Empty):
            self.to_track[cyl,side] = track


    def get_image(self) -> bytes:

        dat, tdat_list = bytearray(), list()

        n_side = max(self.to_track.keys(), default=(0,0), key=lambda x:x[1])[1]
        n_side += 1

        n_cyl = max(self.to_track.keys(), default=(0,0), key=lambda x:x[0])[0]
        n_cyl += 1

        dat += struct.pack('<34s13sx2B2x',
                           b'EXTENDED CPC DSK File\r\nDisk-Info\r\n',
                           ('GW %s' % __version__).encode(),
                           n_cyl, n_side)

        for c in range(n_cyl):

            for h in range(n_side):

                # Empty track: NUL in Track Size Table
                if (c,h) not in self.to_track:
                    dat += b'\x00'
                    continue

                # TODO: Handle FM, and non-DD data rates
                t = self.to_track[c,h]
                assert isinstance(t, ibm.IBMTrack)
                error.check(t.mode is ibm.Mode.MFM,
                            'EDSK: Cannot handle %s track format' % t.mode)
                error.check(0.4e-6 < t.clock < 2.1e-6,
                            'EDSK: Cannot handle %.2fus clock' % (t.clock*1e6))

                if t.clock < 0.75e-6:
                    rate = EDSKRate.ExtendedDensity
                elif t.clock < 1.5e-6:
                    rate = EDSKRate.HighDensity
                else:
                    # Double Density, but we'll just mark it as default (0)
                    rate = 0

                # Estimate sec_sz from size of first sector only.
                # Estimate gap3 from gap between first two sectors.
                n_sec, sec_sz, gap3 = len(t.sectors), 0, 0
                if n_sec > 0:
                    sec_sz = t.sectors[0].idam.n
                    gap3 = ibm.MFMGaps.gap3[t.sectors[0].idam.n]
                if n_sec > 1:
                    gap3 = t.sectors[1].start - t.sectors[0].end
                    gap3 = max(0, round(gap3 / 16) - t.gap_presync)
                tdat = struct.pack('<12s4x8B',
                                   b'Track-Info\r\n', c, h, rate, 0,
                                   sec_sz, n_sec, gap3, 0xe5)

                # Track Information Block
                for s in t.sectors:
                    tdat += struct.pack('<6BH',
                                        s.idam.c, s.idam.h, s.idam.r, s.idam.n,
                                        0, 0, ibm.sec_sz(s.idam.n))
                tdat += bytes(-len(tdat) & 255)

                # Track Data
                for s in t.sectors:
                    tdat += s.dam.data[:]

                # Track Size Table
                assert (len(tdat) & 255) == 0
                dat += struct.pack('B', len(tdat) // 256)

                tdat_list.append(tdat)

        # Pad and concatenate the whole image together.
        dat += bytes(-len(dat) & 255)
        for tdat in tdat_list:
            dat += tdat

        return dat


# Local variables:
# python-indent: 4
# End:
