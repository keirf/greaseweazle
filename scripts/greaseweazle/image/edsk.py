# greaseweazle/image/edsk.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
# 
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import binascii, math, struct
import itertools as it
from bitarray import bitarray

from greaseweazle import error
from greaseweazle.codec.ibm import mfm
from greaseweazle.track import MasterTrack, RawTrack
from .image import Image

class EDSKTrack:

    gap_presync = 12
    gap_4a = 80 # Post-Index
    gap_1  = 50 # Post-IAM
    gap_2  = 22 # Post-IDAM

    gapbyte = 0x4e
    
    def __init__(self):
        self.time_per_rev = 0.2
        self.clock = 2e-6
        self.bits, self.weak = [], []

    def raw_track(self):
        track = MasterTrack(
            bits = self.bits,
            time_per_rev = self.time_per_rev,
            weak = self.weak)
        track.verify = self
        track.verify_revs = 1
        return track

    def _find_sync(self, bits, sync, start):
        for offs in bits.itersearch(sync):
            if offs >= start:
                return offs
        return None
    
    def verify_track(self, flux):
        flux.cue_at_index()
        raw = RawTrack(clock = self.clock, data = flux)
        bits, _ = raw.get_all_data()
        weak_iter = it.chain(self.weak, [(self.verify_len+1,1)])
        weak = next(weak_iter)

        # Start checking from the IAM sync
        dump_start = self._find_sync(bits, mfm.iam_sync, 0)
        self_start = self._find_sync(self.bits, mfm.iam_sync, 0)

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
            dump_start = self._find_sync(bits, mfm.sync, dump_end)
            self_start = self._find_sync(self.bits, mfm.sync, self_end)

        # Did we verify all regions in the pristine track?
        return self_start is None

class EDSK(Image):

    read_only = True
    default_format = 'ibm.mfm'

    def __init__(self):
        self.to_track = dict()

    # Currently only finds one weak range.
    @staticmethod
    def find_weak_ranges(dat, size):
        orig = dat[:size]
        s, e = size, 0
        for i in range(1, len(dat)//size):
            diff = [x^y for x, y in zip(orig, dat[size*i:size*(i+1)])]
            weak = [idx for idx, val in enumerate(diff) if val != 0]
            if weak:
                s, e = min(s, weak[0]), max(e, weak[-1])
        return [(s,e-s+1)] if s <= e else []
        
    @classmethod
    def from_file(cls, name):

        with open(name, "rb") as f:
            dat = f.read()

        edsk = cls()

        sig, creator, ncyls, nsides, track_sz = struct.unpack(
            '<34s14s2BH', dat[:52])
        if sig[:8] == b'MV - CPC':
            extended = False
        elif sig[:16] == b'EXTENDED CPC DSK':
            extended = True
        else:
            raise error.Fatal('Unrecognised CPC DSK file: bad signature')

        if extended:
            tsizes = list(dat[52:52+ncyls*nsides])
            tsizes = list(map(lambda x: x*256, tsizes))
        else:
            raise error.Fatal('Standard CPC DSK file not yet supported')

        o = 256 # skip disk header and track-size table
        for tsize in tsizes:
            if tsize == 0:
                continue
            sig, cyl, head, sec_sz, nsecs, gap_3, filler = struct.unpack(
                '<12s4x2B2x4B', dat[o:o+24])
            error.check(sig == b'Track-Info\r\n',
                        'EDSK: Missing track header')
            error.check((cyl, head) not in edsk.to_track,
                        'EDSK: Track specified twice')
            while True:
                track = EDSKTrack()
                t = bytes()
                # Post-index gap
                t += mfm.encode(bytes([track.gapbyte] * track.gap_4a))
                # IAM
                t += mfm.encode(bytes(track.gap_presync))
                t += mfm.iam_sync_bytes
                t += mfm.encode(bytes([mfm.IBM_MFM.IAM]))
                t += mfm.encode(bytes([track.gapbyte] * track.gap_1))
                secs = dat[o+24:o+24+8*nsecs]
                data_pos = o + 256 # skip track header and sector-info table
                while secs:
                    c, h, r, n, stat1, stat2, actual_length = struct.unpack(
                        '<6BH', secs[:8])
                    secs = secs[8:]
                    size = 128 << n
                    weak = []
                    if size != actual_length:
                        error.check(actual_length != 0
                                    and actual_length % size == 0,
                                    'EDSK: Weird sector size (GAP protection?)')
                        weak = cls().find_weak_ranges(
                            dat[data_pos:data_pos+actual_length], size)
                    # Update CRCs according to status flags
                    icrc, dcrc = 0, 0
                    if stat1 & 0x20:
                        if stat2 & 0x20:
                            dcrc = 0xffff
                        else:
                            icrc = 0xffff
                        stat1 &= ~0x20
                        stat2 &= ~0x20
                    # Update address marks according to status flags
                    imark, dmark = mfm.IBM_MFM.IDAM, mfm.IBM_MFM.DAM
                    if stat2 & 0x40:
                        dmark = mfm.IBM_MFM.DDAM
                    if stat2 & 0x01:
                        dmark = 0
                    elif stat1 & 0x01:
                        imark = 0
                    stat1 &= ~0x01
                    stat2 &= ~0x41
                    error.check(stat1 == 0 and stat2 == 0,
                                'EDSK: Mangled sector (copy protection?)')
                    sec_data = dat[data_pos:data_pos+size]
                    data_pos += actual_length
                    # IDAM
                    t += mfm.encode(bytes(track.gap_presync))
                    t += mfm.sync_bytes
                    am = bytes([0xa1, 0xa1, 0xa1, imark, c, h, r, n])
                    am += struct.pack('>H', mfm.crc16.new(am).crcValue^icrc)
                    t += mfm.encode(am[3:])
                    t += mfm.encode(bytes([track.gapbyte] * track.gap_2))
                    # DAM
                    t += mfm.encode(bytes(track.gap_presync))
                    t += mfm.sync_bytes
                    track.weak += [((s+len(t)//2+4)*16, n*16) for s,n in weak]
                    am = bytes([0xa1, 0xa1, 0xa1, dmark]) + sec_data
                    am += struct.pack('>H', mfm.crc16.new(am).crcValue^dcrc)
                    t += mfm.encode(am[3:])
                    t += mfm.encode(bytes([track.gapbyte] * gap_3))

                # Some EDSK images have bogus GAP3 values. If the track is too
                # long to comfortably fit in 300rpm at double density, shrink
                # GAP3 as far as necessary.
                tracklen = int((track.time_per_rev / track.clock) / 16)
                overhang = int(len(t)//2 - tracklen*0.99)
                if overhang <= 0:
                    break
                new_gap_3 = gap_3 - math.ceil(overhang / nsecs)
                error.check(new_gap_3 >= 0,
                            'EDSK: Track %d.%d is too long '
                            '(%d bits @ GAP3=%d; %d bits @ GAP3=0)'
                            % (cyl, head, len(t)*8, gap_3,
                               (len(t)//2-gap_3*nsecs)*16))
                gap_3 = new_gap_3

            # Pre-index gap
            track.verify_len = len(t)*8
            gap = tracklen - len(t)//2
            t += mfm.encode(bytes([track.gapbyte] * gap))

            track.bits = bitarray(endian='big')
            track.bits.frombytes(mfm.mfm_encode(t))
            edsk.to_track[cyl,head] = track
            o += tsize

        return edsk


    def get_track(self, cyl, side):
        if (cyl,side) not in self.to_track:
            return None
        return self.to_track[cyl,side].raw_track()


# Local variables:
# python-indent: 4
# End:
