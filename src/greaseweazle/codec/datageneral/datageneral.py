# greaseweazle/codec/datageneral.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.

from typing import List, Optional

import struct
from bitarray import bitarray
import crcmod.predefined
import itertools as it
from enum import Enum

from greaseweazle import error
from greaseweazle.codec import codec
from greaseweazle.codec.ibm.ibm import decode, encode, fm_encode, mfm_encode
from greaseweazle.track import MasterTrack, PLL, PLLTrack
from greaseweazle.flux import HasFlux

default_revs = 1

bad_sector = b'-=[BAD SECTOR]=-'

mfm_sync = bitarray(endian='big')
mfm_sync.frombytes(mfm_encode(encode(b'\x00\xfb')))

fm_sync = bitarray(endian='big')
fm_sync.frombytes(fm_encode(encode(b'\x00\x00\x00\x00\x00\x01')))


#Sector starts with 23 * 16 zero bits, then a 0001 sync word followed by the adress field
#There is an 18us "splice" between the address field and the following data field sync 
#The documentation is not very clear on the exact number of bits in the data sync field
#The splice plus the data sync add up to a non-integer number of bits, so we 
#need to search for the data sync pattern to locate the data

#"Manual" FM encoding....
fm_datasync = bitarray("101010101010101010101010101010101010101010101010101010101011")


def csum(dat):
    #CRC with poly x^16 + x^8 + 1
    
    y = 0
    #Need to "clock in" 8 extra bits to get the correct result    
    for x in dat + b'\x00':
        y = ((y & 0xFF) ^ (y >> 8)) |  (((y & 0xFF) ^ x) << 8)
    return y

class Mode(Enum):
    FM, MFM = range(2)
    def __str__(self):
        NAMES = [ 'Data General FM', 'Data General MFM' ]
        return f'{NAMES[self.value]}'

class DataGeneral(codec.Codec):

    time_per_rev = 0.166

    verify_revs: float = default_revs

    def __init__(self, cyl: int, head: int, config):
        if config.mode is Mode.FM:
            self.clock = 2e-6
            self.bps = 512
            self.sync = fm_sync
            self.datasync = fm_datasync
            self.presync_bytes = 21
            self.sync_bytes = 6
        else:
            self.clock = 2e-6
            self.bps = 512
            self.sync = mfm_sync
            self.presync_bytes = 34
            self.sync_bytes = 2
        self.cyl, self.head = cyl, head
        self.config = config
        self.sector: List[Optional[bytes]]
        self.sector = [None] * self.nsec

    @property
    def nsec(self) -> int:
        return self.config.secs

    def summary_string(self) -> str:
        nsec, nbad = self.nsec, self.nr_missing()
        s = "%s (%d/%d sectors)" % (self.config.mode, nsec - nbad, nsec)
        return s

    # private
    def add(self, sec_id, data) -> None:
        assert not self.has_sec(sec_id)
        self.sector[sec_id] = data

    def has_sec(self, sec_id: int) -> bool:
        return self.sector[sec_id] is not None

    def nr_missing(self) -> int:
        return len([sec for sec in self.sector if sec is None])

    def get_img_track(self) -> bytearray:
        tdat = bytearray()
        for sec in self.sector:
            tdat += sec if sec is not None else bad_sector * (self.bps//16)
        return tdat

    def set_img_track(self, tdat: bytes) -> int:
        totsize = self.nsec * self.bps
        if len(tdat) < totsize:
            tdat += bytes(totsize - len(tdat))
        for sec in range(self.nsec):
            self.sector[sec] = tdat[sec*self.bps:(sec+1)*self.bps]
        return totsize

    def decode_flux(self, track: HasFlux, pll: Optional[PLL]=None) -> None:
        flux = track.flux()
        if flux.time_per_rev < self.time_per_rev / 2:
            flux.identify_hard_sectors()
        flux.cue_at_index()
        raw = PLLTrack(time_per_rev = self.time_per_rev,
                       clock = self.clock, data = flux, pll = pll)

        for rev in range(len(raw.revolutions)):

            if self.nr_missing() == 0:
                break

            bits, _ = raw.get_revolution(rev)

            hardsector_bits = raw.revolutions[rev].hardsector_bits
            if hardsector_bits is not None:
                hardsector_bits = list(it.accumulate(hardsector_bits))
            else:
                hardsector_bits = [len(bits)*(i+1)//self.nsec
                                   for i in range(self.nsec)]
            error.check(len(hardsector_bits) == self.nsec,
                        f'Data General: Unexpected number of sectors: '
                        f'{len(hardsector_bits)}')
            hardsector_bits = [0] + hardsector_bits

            for sec_id in range(self.nsec):

                if self.has_sec(sec_id):
                    continue

                s, e = hardsector_bits[sec_id], hardsector_bits[sec_id+1]
                #print(bits[s:e])
                data = decode(bits[s:e].tobytes())
                #print(data.hex())
                offs = bits[s:e].search(self.sync)
                if (off := next(offs, None)) is None:
                    continue
                off += (self.sync_bytes) * 16
                data = decode(bits[s+off:s+off+2*16].tobytes())
                #print(data.hex())
                track = data[0] & 0x7F
                sector = data[1] >> 2
                #print(f'Track {track}, Sector {sector}')

                
                dataoffs = bits[s+off+2*16:e].search(self.datasync)
                
                if (dataoff := next(dataoffs, None)) is None:
                    continue

                data = decode(bits[s+off+2*16 + dataoff + len(self.datasync) :s+off+2*16 + dataoff + len(self.datasync) + 518*16].tobytes())
                #print(data[:512].hex())
                #print(data[512:514].hex())
                #print(data[514:].hex())
                #print(hex(csum(data[:512])))
                if  csum(data[:512])== int.from_bytes(data[512:514], 'big'):
                    self.add(sec_id, data[:512])
                else:
                    pass
                


    def master_track(self) -> MasterTrack:
        raise error.Fatal('NOT IMPLEMENTED')
        t = bytes()
        slen = int((self.time_per_rev / self.clock / self.nsec / 16))

        for sec_id in range(self.nsec):
            s  = encode(bytes(self.presync_bytes))
            s += encode(b'\xfb' * self.sync_bytes)
            sector = self.sector[sec_id]
            data = bad_sector*(self.bps//16) if sector is None else sector
            s += encode(data + bytes([csum(data)]))
            s += encode(bytes(slen - len(s)//2))
            t += s

        t = mfm_encode(t) if self.config.mode is Mode.MFM else fm_encode(t)

        hardsector_bits = [slen*16*i for i in range(self.nsec)]

        track = MasterTrack(bits = t, time_per_rev = self.time_per_rev)
        track.verify = self
        return track


    def verify_track(self, flux):
        readback_track = self.__class__(self.cyl, self.head, self.config)
        readback_track.decode_flux(flux)
        return (readback_track.nr_missing() == 0
                and self.sector == readback_track.sector)


class DataGeneralDef(codec.TrackDef):

    default_revs = default_revs

    def __init__(self, format_name: str):
        self.mode: Optional[Mode] = None
        self.secs: Optional[int] = None
        self.finalised = False

    def add_param(self, key: str, val) -> None:
        if key == 'secs':
            val = int(val)
            self.secs = val
        elif key == 'mode':
            if val == 'fm':
                self.mode = Mode.FM
            elif val == 'mfm':
                self.mode = Mode.MFM
            else:
                raise error.Fatal('unrecognised mode %s' % val)
        else:
            raise error.Fatal('unrecognised track option %s' % key)

    def finalise(self) -> None:
        if self.finalised:
            return
        error.check(self.secs is not None,
                    'number of sectors not specified')
        error.check(self.mode is not None,
                    'mode not specified')
        self.finalised = True

    def mk_track(self, cyl: int, head: int) -> DataGeneral:
        return DataGeneral(cyl, head, self)


# Local variables:
# python-indent: 4
# End:
