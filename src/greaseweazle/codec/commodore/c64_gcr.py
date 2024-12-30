# greaseweazle/codec/c64/c64_gcr.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from typing import List, Optional, Tuple

import struct
from bitarray import bitarray

from greaseweazle import error
from greaseweazle import optimised
from greaseweazle.codec import codec
from greaseweazle.track import MasterTrack, PLL, PLLTrack
from greaseweazle.flux import Flux, HasFlux

default_revs = 1.1

# GCR 0xffd49 = ...11111 01010 01001 = [sync] A 9 -> [sync] 08 (hdr block id)
sector_sync = bitarray(endian='big')
sector_sync.frombytes(b'\xff\xd4\x90')
sector_sync = sector_sync[:20]

# GCR 0xffd57 = ...11111 01010 10111 = [sync] A 17 -> [sync] 07 (data block id)
data_sync = bitarray(endian='big')
data_sync.frombytes(b'\xff\xd5\x70')
data_sync = data_sync[:20]

bad_sector = b'-=[BAD SECTOR]=-' * 16

class C64GCR(codec.Codec):

    time_per_rev = 0.2

    verify_revs = default_revs

    def __init__(self, cyl: int, head: int, config):
        self.cyl, self.head = cyl, head
        self.config = config
        self.clock = config.clock
        self.sector: List[Optional[bytes]]
        self.sector = [None] * self.nsec
        self.disk_id: Optional[int] = None
        error.check(optimised.enabled,
                    'Commodore GCR requires optimised C extension')

    @property
    def nsec(self) -> int:
        return self.config.secs

    def summary_string(self) -> str:
        nsec, nbad = self.nsec, self.nr_missing()
        s = "Commodore GCR (%d/%d sectors)" % (nsec - nbad, nsec)
        return s

    def set_disk_id(self, disk_id: int):
        assert self.disk_id is None
        self.disk_id = disk_id

    # private
    def add(self, sec_id, data) -> None:
        assert not self.has_sec(sec_id)
        self.sector[sec_id] = data

    # private
    def tracknr(self) -> int:
        return self.head*35 + self.cyl + 1

    def has_sec(self, sec_id: int) -> bool:
        return self.sector[sec_id] is not None

    def nr_missing(self) -> int:
        return len([sec for sec in self.sector if sec is None])

    def get_img_track(self) -> bytearray:
        tdat = bytearray()
        for sec in self.sector:
            tdat += sec if sec is not None else bad_sector
        return tdat

    def set_img_track(self, tdat: bytes) -> int:
        totsize = self.nsec * 256
        if len(tdat) < totsize:
            tdat += bytes(totsize - len(tdat))
        for sec in range(self.nsec):
            self.sector[sec] = tdat[sec*256:(sec+1)*256]
        return totsize

    def decode_flux(self, track: HasFlux, pll: Optional[PLL]=None) -> None:
        raw = PLLTrack(time_per_rev = self.time_per_rev,
                       clock = self.clock, data = track, pll = pll,
                       lowpass_thresh = 2.5e-6)
        bits, _ = raw.get_all_data()

        for offs in bits.search(sector_sync):

            if self.nr_missing() == 0:
                break

            # Decode header, 8 bytes (=10 bytes GCR):
            # 0x08, csum, sector, track, disk_id[2], gap[2]
            offs += 10
            sec = bits[offs:offs+10*8].tobytes()
            if len(sec) != 10:
                continue
            hdr = optimised.decode_c64_gcr(sec)
            sum = 0
            for x in hdr[1:6]:
                sum ^= x
            if sum != 0:
                continue
            sec_id, cyl, disk_id = struct.unpack('>2BH', hdr[2:6])
            if (cyl != self.tracknr() or sec_id >= self.nsec):
                print('T%d.%d: Ignoring unexpected sector C:%d S:%d ID:%04x'
                      % (self.cyl, self.head, cyl, sec_id, disk_id))
                continue
            if self.disk_id is None:
                self.disk_id = disk_id
            elif self.disk_id != disk_id:
                print('T%d.%d: Expected ID %04x in sector C:%d S:%d ID:%04x'
                      % (self.cyl, self.head, self.disk_id,
                         cyl, sec_id, disk_id))
                continue
            if self.has_sec(sec_id):
                continue

            # Find data
            offs += 8*8
            dat_offs = list(bits[offs:offs+100*8].search(data_sync))
            if len(dat_offs) != 1:
                continue
            offs += dat_offs[0]

            # Decode data, 260 bytes (=325 bytes GCR):
            # 0x07, data[256], csum, gap[2]
            offs += 10
            sec = bits[offs:offs+260*10].tobytes()
            if len(sec) != 325:
                continue
            sec = optimised.decode_c64_gcr(sec)
            sum = 0
            for x in sec[1:258]:
                sum ^= x
            if sum != 0:
                continue

            self.add(sec_id, sec[1:257])


    def master_track(self) -> MasterTrack:

        # Post-index track gap.
        t = bytes([0x55] * 10)

        for sec_id in range(self.nsec):
            sector = self.sector[sec_id]
            data = bad_sector if sector is None else sector
            # Header
            disk_id = self.disk_id if self.disk_id is not None else 0
            hdr = struct.pack('>2BH', sec_id, self.tracknr(), disk_id)
            sum = 0
            for x in hdr:
                sum ^= x
            hdr = bytes([0x08, sum]) + hdr + bytes([0x0f, 0x0f])
            t += b'\xff' * 5 # sync
            t += optimised.encode_c64_gcr(hdr)
            t += b'\x55' * 9 # gap
            # Data
            t += b'\xff' * 5 # sync
            sum = 0
            for x in data:
                sum ^= x
            t += optimised.encode_c64_gcr(
                bytes([0x07]) + data + bytes([sum, 0x0f, 0x0f]))
            t += b'\x55' * 9 # gap

        # Add the pre-index gap.
        tlen = int((self.time_per_rev / self.clock)) & ~31
        t += bytes([0x55] * (tlen//8-len(t)))

        track = MasterTrack(bits = t, time_per_rev = self.time_per_rev)
        track.verify = self
        return track


    def verify_track(self, flux):
        readback_track = self.__class__(self.cyl, self.head, self.config)
        readback_track.decode_flux(flux)
        return (readback_track.nr_missing() == 0
                and self.sector == readback_track.sector)


class C64GCRDef(codec.TrackDef):

    default_revs = default_revs

    def __init__(self, format_name: str):
        self.secs: Optional[int] = None
        self.clock: Optional[float] = None
        self.finalised = False

    def add_param(self, key: str, val) -> None:
        if key == 'secs':
            val = int(val)
            self.secs = val
        elif key == 'clock':
            val = float(val)
            self.clock = val * 1e-6
        else:
            raise error.Fatal('unrecognised track option %s' % key)

    def finalise(self) -> None:
        if self.finalised:
            return
        error.check(self.secs is not None,
                    'number of sectors not specified')
        error.check(self.clock is not None,
                    'clock period not specified')
        self.finalised = True

    def mk_track(self, cyl: int, head: int) -> C64GCR:
        return C64GCR(cyl, head, self)


# Local variables:
# python-indent: 4
# End:
