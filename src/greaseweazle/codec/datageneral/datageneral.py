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
from greaseweazle.codec.ibm.ibm import decode, encode, fm_encode
from greaseweazle.track import MasterTrack, PLL, PLLTrack
from greaseweazle.flux import HasFlux

default_revs = 1

bad_sector = b'-=[BAD SECTOR]=-'

min_sync = 1000
max_sync = 0
min_sync_zero = 1000
max_sync_zero = 0
min_datasync = 1000
max_datasync = 0




def csum(dat):
    #CRC with poly x^16 + x^8 + 1
    
    y = 0
    #Need to "clock in" 8 extra bits to get the correct result    
    for x in dat + b'\x00':
        y = ((y & 0xFF) ^ (y >> 8)) |  (((y & 0xFF) ^ x) << 8)
    return y

class Mode(Enum):
    FM = 0
    def __str__(self):
        NAMES = [ 'Data General FM']
        return f'{NAMES[self.value]}'

class DataGeneral(codec.Codec):
    '''
            Data General 8" floppy disk format, from DG document 015-000088-00, flowchart page G-4
            
            Sector read:
            <sector index pulse> <704uS delay> <sector address sync bit> <16 bits sector address (preamble) <20 uS delay> <64 uS delay> <data sync bit> <data 512 bits><crc 16 bits>

            Sector write:
            <sector index pulse> <704uS delay> <sector address sync bit> <16 bits sector address (preamble) <20 uS delay> <write zeros for 160 uS -> 40 zero bits> <data sync bit> <data 512 bits><crc 16 bits>

            Formatting operation:
            <sector index pulse> <160 uS delay> <352 bits '0'> <0000000000000001> <16 bits sector address> <352 bits '0'> <3520 bits 'dont care'>

            The actual number of zero bits before the sector address sync bit observed in disk images varies between 572 and 740
            
    '''        
    
    time_per_rev = 0.166

    verify_revs: float = default_revs

    def __init__(self, cyl: int, head: int, config):
        
        self.clock = 2e-6
        self.bps = 512

        self.address_sync = b'\x00\x01'
        self.data_sync = b'\x00\x01'

        self.address_sync_fmbits = bitarray(endian='big')
        self.address_sync_fmbits.frombytes(fm_encode(encode(self.address_sync)))

        self.data_sync_fmbits = bitarray(endian='big')
        self.data_sync_fmbits.frombytes(fm_encode(encode(self.data_sync)))
        
        #According to the documentation, there is a 704uS delay before the drive reads the sync word for the sector address (preamble)
        #This is equivalent to 704 presync FM bits followed by 0x0001 (32 FM bits) sync word
        #The actual number of FM bits before the sector address sync word observed in disk images varies between 572 and 740
        self.pre_addresssync_read_fm_bits = 560
        #self.pre_addresssync_read_fm_bits = 100
        
        #self.pre_addresssync_write_fm_bits = 704
        self.pre_addresssync_write_fm_bytes = 44

        #there is a 20us + 64us delay before the data sync bit is read corresponding to a total of 84 FM bits + 2 fm sync bits
        #When writing, there is a 20uS delay, then 40 zero bits followed by a one bit (the sync bit) are written
        #The actual number of zero (FM) bits before the data sync bit observed in disk images varies between 97 and 98
        #equivalent to 66 FM bits followed by 0x0001 (32 FM bits) syncword. For reading, use minimum of 60 FM bits before the syncword
        
        self.pre_datasync_read_fm_bits = 60
        #self.pre_datasync_write_fm_bits = 150 #20 + 160 + 2 = 150 presync + 32 sync word 0x0001
        self.pre_datasync_write_fm_bytes = 5 #20 + 160 + 2 = 150 presync + 32 sync word 0x0001
    

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
        global min_sync
        global max_sync
        global min_sync_zero
        global max_sync_zero
        global min_datasync
        global max_datasync

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

                #Start searching for sync after a minimum delay of pre_addresssync_read_bits
                offs = bits[s + self.pre_addresssync_read_fm_bits:e].search(self.address_sync_fmbits)
                if (off := next(offs, None)) is None:
                    continue

                numsync = self.pre_addresssync_read_fm_bits + off + len(self.address_sync_fmbits)
                #Get offset of first preamble bit
                off += self.pre_addresssync_read_fm_bits +  len(self.address_sync_fmbits)


                #Reed 2 byte preamb;e
                data = decode(bits[s+off:s+off+2*16].tobytes())
                
                #Extract track# and sector#
                track = data[0] & 0x7F
                sector = data[1] >> 2
                
                
                if numsync < min_sync:
                    min_sync =numsync
                if numsync > max_sync:
                    max_sync = numsync

                numsynczero = 0
                
                for kk in range(s + numsync - 4, s, -2):
                    if bits[kk:kk + 2] != bitarray('10'):
                        break
                    numsynczero += 2

                if numsynczero < min_sync_zero:
                    min_sync_zero =numsynczero
                if numsynczero > max_sync_zero:
                    max_sync_zero = numsynczero
                #print(f'Track {track}, Sector {sector}, after {numsync} sync bits, {numsynczero} zero value sync bits, min sync {min_sync}, max sync {max_sync}, min zero {min_sync_zero}, max zero {max_sync_zero}')

                dsyncstart = off + 2*16
                #Skip to the start of the data sync, skip over 2 byte preamble plus minimum delay of pre_datasync_read_bits
                off +=  2*16 + self.pre_datasync_read_fm_bits
                dataoffs = bits[s+off:e].search(self.data_sync_fmbits)
                
                if (dataoff := next(dataoffs, None)) is None:
                    continue
    
                dataoff += off + len(self.data_sync_fmbits)
                numdsync = dataoff - dsyncstart

                if numdsync < min_datasync:
                    min_datasync = numdsync
                if numdsync > max_datasync:
                    max_datasync = numdsync

                #print(f'Data sync {numdsync} bits, min {min_datasync}, max {max_datasync}')

                data = decode(bits[s + dataoff:s + dataoff + 518*16].tobytes())
                #print(data[:512].hex())
                #print(data[512:514].hex())
                #print(data[514:].hex())
                #print(hex(csum(data[:512])))
                if  csum(data[:512])== int.from_bytes(data[512:514], 'big'):
                    self.add(sec_id, data[:512])
                else:
                    pass
                


    def master_track(self) -> MasterTrack:
        t = bytes()
        slen = int((self.time_per_rev / self.clock / self.nsec / 16))

        for sec_id in range(self.nsec):
            # 
            s  = encode(b'\x00' * self.pre_addresssync_write_fm_bytes)
            s += encode(self.address_sync)
            
            
            
            sector = self.sector[sec_id]
            trackid = self.cyl & 7
            sectorenc = (sec_id & 0xF) << 2
            preamble = struct.pack('>BB', trackid, sectorenc)
            
            s += encode(preamble)

            s += encode(b'\x00' * self.pre_datasync_write_fm_bytes)
            s += encode(self.data_sync)
            
            data = bad_sector*(self.bps//16) if sector is None else sector
            
            s += encode(data + csum(data).to_bytes(2, 'big'))
            s += encode(bytes(slen - len(s)//2))
            t += s

        t = fm_encode(t)

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
