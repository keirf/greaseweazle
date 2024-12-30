# greaseweazle/codec/apple2/apple2_gcr.py
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

gap4 = bitarray([1], endian='big')
ff40 = bitarray([1]*8 + [0]*2, endian='big')
ff32 = ff40[:8]

addr_sync = bitarray(endian='big')
addr_sync.frombytes(b'\xd5\xaa\x96')

data_sync = bitarray(endian='big')
data_sync.frombytes(b'\xd5\xaa\xad')

trailer = bitarray(endian='big')
trailer.frombytes(b'\xde\xaa\xeb')

bad_sector = b'-=[BAD SECTOR]=-' * 16

class Apple2GCR(codec.Codec):

    time_per_rev = 0.2

    verify_revs = default_revs

    def __init__(self, cyl: int, head: int, config):
        self.cyl, self.head = cyl, head
        self.config = config
        self.clock = config.clock
        self.sector: List[Optional[bytes]]
        self.sector = [None] * self.nsec
        self.vol_id: Optional[int] = None
        error.check(optimised.enabled,
                    'Apple2 GCR requires optimised C extension')

    @property
    def nsec(self) -> int:
        return len(self.config.secs)

    def summary_string(self) -> str:
        nsec, nbad = self.nsec, self.nr_missing()
        s = "Apple2 GCR (%d/%d sectors)" % (nsec - nbad, nsec)
        return s

    def set_vol_id(self, vol_id: int):
        assert self.vol_id is None
        self.vol_id = vol_id

    # private
    def add(self, sec_id, data) -> None:
        assert not self.has_sec(sec_id)
        self.sector[sec_id] = data

    # private
    def tracknr(self) -> int:
        return self.cyl

    def has_sec(self, sec_id: int) -> bool:
        return self.sector[sec_id] is not None

    def nr_missing(self) -> int:
        return len([sec for sec in self.sector if sec is None])

    def get_img_track(self) -> bytearray:
        tdat = bytearray()
        for i in self.config.secs:
            sec = self.sector[i]
            tdat += sec if sec is not None else bad_sector
        return tdat

    def set_img_track(self, tdat: bytes) -> int:
        totsize = self.nsec * 256
        if len(tdat) < totsize:
            tdat += bytes(totsize - len(tdat))
        for i,sec in enumerate(self.config.secs):
            self.sector[sec] = tdat[i*256:(i+1)*256]
        return totsize

    def decode_flux(self, track: HasFlux, pll: Optional[PLL]=None) -> None:
        raw = PLLTrack(time_per_rev = self.time_per_rev,
                       clock = self.clock, data = track, pll = pll,
                       lowpass_thresh = 2.5e-6)
        bits, _ = raw.get_all_data()

        for offs in bits.search(addr_sync):

            if self.nr_missing() == 0:
                break

            # Decode header
            offs += 3*8
            sec = bits[offs:offs+8*8].tobytes()
            if len(sec) != 8:
                continue
            hdr = map(lambda x: (x & x>>7) & 255,
                      list(struct.unpack('>4H', sec)))
            vol_id, trk_id, sec_id, csum = tuple(hdr)

            # Validate header
            if csum != vol_id ^ trk_id ^ sec_id:
                continue
            if (trk_id != self.tracknr() or sec_id >= self.nsec):
                print('T%d.%d: Ignoring unexpected sector C:%d S:%d ID:%04x'
                      % (self.cyl, self.head, trk_id, sec_id, vol_id))
                continue
            if self.vol_id is None:
                self.vol_id = vol_id
            elif self.vol_id != vol_id:
                print('T%d.%d: Expected ID %04x in sector C:%d S:%d ID:%04x'
                      % (self.cyl, self.head, self.vol_id,
                         trk_id, sec_id, vol_id))
                continue
            if self.has_sec(sec_id):
                continue

            # Find data
            offs += 8*8
            dat_offs = list(bits[offs:offs+100*8].search(data_sync))
            if len(dat_offs) != 1:
                continue
            offs += dat_offs[0]

            # Decode data
            sec, csum = optimised.decode_apple2_sector(
                bits[offs+3*8:offs+400*8].tobytes())
            if csum != 0:
                continue

            self.add(sec_id, sec)


    def master_track(self) -> MasterTrack:

        vol_id = self.vol_id if self.vol_id is not None else 254
        trk_id = self.tracknr()

        # Post-index track gap.
        t = gap4 * 300

        for sec_id in range(self.nsec):
            sector = self.sector[sec_id]
            data = bad_sector if sector is None else sector
            t += ff40*18 + ff32 + addr_sync
            t.frombytes(b''.join(map(
                lambda x: bytes([x>>1 | 0xaa, x | 0xaa]),
                [vol_id, trk_id, sec_id, vol_id ^ trk_id ^ sec_id])))
            t += trailer + ff40*6 + data_sync
            t.frombytes(optimised.encode_apple2_sector(data))
            t += trailer

        # Add the pre-index gap.
        tlen = int((self.time_per_rev / self.clock))
        t += gap4 * (tlen-len(t))

        track = MasterTrack(bits = t, time_per_rev = self.time_per_rev)
        track.verify = self
        return track


    def verify_track(self, flux):
        readback_track = self.__class__(self.cyl, self.head, self.config)
        readback_track.decode_flux(flux)
        return (readback_track.nr_missing() == 0
                and self.sector == readback_track.sector)


class Apple2GCRDef(codec.TrackDef):

    default_revs = default_revs

    def __init__(self, format_name: str):
        self.secs: List[int] = []
        self.clock: Optional[float] = None
        self.finalised = False

    def add_param(self, key: str, val) -> None:
        if key == 'secs':
            self.secs = []
            for x in val.split(','):
                self.secs.append(int(x))
            rsecs = [-1] * len(self.secs)
            for i,x in enumerate(self.secs):
                error.check(x < len(rsecs), f'sector {x} is out of range')
                error.check(rsecs[x] == -1, f'sector {x} is repeated')
                rsecs[x] = i
        elif key == 'clock':
            val = float(val)
            self.clock = val * 1e-6
        else:
            raise error.Fatal('unrecognised track option %s' % key)

    def finalise(self) -> None:
        if self.finalised:
            return
        error.check(self.secs,
                    'sector list not specified')
        error.check(self.clock is not None,
                    'clock period not specified')
        self.finalised = True

    def mk_track(self, cyl: int, head: int) -> Apple2GCR:
        return Apple2GCR(cyl, head, self)


# Local variables:
# python-indent: 4
# End:
