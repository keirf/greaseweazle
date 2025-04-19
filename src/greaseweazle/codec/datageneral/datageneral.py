# greaseweazle/codec/datageneral/datageneral.py
#
# Data General 8" floppy disk format, from DG document 015-000088-00
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.

from typing import List, Optional

import struct, binascii # XXX
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

sync_word = b'\x00\x01'
sync = bitarray(endian='big')
sync.frombytes(fm_encode(encode(sync_word)))

# CRC with poly x^16 + x^8 + 1
def csum(dat):
    y = 0
    # Need to "clock in" 8 extra bits to get the correct result
    for x in dat + b'\x00':
        y = ((y & 0xFF) ^ (y >> 8)) | (((y & 0xFF) ^ x) << 8)
    return y

class DataGeneral(codec.Codec):

    nsec = 8
    time_per_rev = 60 / 360

    verify_revs: float = default_revs

    def __init__(self, cyl: int, head: int, config):
        self.clock = 2e-6
        self.bps = 512
        self.cyl, self.head = cyl, head
        self.config = config
        self.sector: List[Optional[bytes]]
        self.sector = [None] * self.nsec

    def summary_string(self) -> str:
        nsec, nbad = self.nsec, self.nr_missing()
        s = "Data General 2F (%d/%d sectors)" % (nsec - nbad, nsec)
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
                # DG hard-sectored media has 4 holes per sector; 8 sectors
                if len(hardsector_bits) == 32:
                    hardsector_bits = hardsector_bits[3::4]
            else:
                hardsector_bits = [len(bits)*(i+1)//self.nsec
                                   for i in range(self.nsec)]
            error.check(len(hardsector_bits) == self.nsec,
                        f'Data General: Unexpected number of sectors: '
                        f'{len(hardsector_bits)}')
            hardsector_bits = [0] + hardsector_bits

            for hsec_id in range(self.nsec):

                s, e = hardsector_bits[hsec_id], hardsector_bits[hsec_id+1]
                # Skip first 352 cells (704us), see Figure G-1
                s += 352

                offs = bits[s:e].search(sync)
                if (off := next(offs, None)) is None:
                    continue
                off += 2*16
                h_off = off

                # Read and check the preamble
                preamble = decode(bits[s+off:s+off+2*16].tobytes())
                if len(preamble) != 2:
                    continue
                cyl = preamble[0] & 0x7F
                sec_id = preamble[1] >> 2
                if cyl != self.cyl or sec_id > self.nsec:
                    print('T%d.%d: Ignoring unexpected sector C:%d R:%d'
                          % (self.cyl, self.head, cyl, sec_id))
                    continue
                if self.has_sec(sec_id):
                    break

                # Skip 40 cells (80us) past the preamble word
                d_off = off + 2*16 + 40
                offs = bits[s+d_off:e].search(sync)
                if (off := next(offs, None)) is None:
                    continue
                off += d_off + 2*16

                # Read and checksum the data
                data = decode(bits[s+off:s+off+514*16].tobytes())
                if len(data) != 514:
                    continue
                read_csum = int.from_bytes(data[512:], 'big')
                if csum(data[:512]) == read_csum:
                    self.add(sec_id, data[:512])


    def master_track(self) -> MasterTrack:
        t = bytes()
        slen = int((self.time_per_rev / self.clock / self.nsec / 16))

        for sec_id in range(self.nsec):
            # Format track layout, Figures F-4 & H-9
            s  = encode(bytes(22*2))
            s += encode(sync_word)

            s += encode(struct.pack('>BB', self.cyl & 0x7f, sec_id << 2))

            # Delay 20us + 160us (Figure G-5) ~= 6 bytes
            s += encode(bytes(4))
            s += encode(sync_word)

            sector = self.sector[sec_id]
            data = bad_sector*(self.bps//16) if sector is None else sector

            s += encode(data + csum(data).to_bytes(2, 'big'))
            s += encode(bytes(slen - len(s)//2))
            t += s

        t = fm_encode(t)

        track = MasterTrack(bits = t, time_per_rev = self.time_per_rev,
                            hardsector_bits = [slen*16] * self.nsec)
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
        return

    def add_param(self, key: str, val) -> None:
        raise error.Fatal('unrecognised track option %s' % key)

    def finalise(self) -> None:
        return

    def mk_track(self, cyl: int, head: int) -> DataGeneral:
        return DataGeneral(cyl, head, self)


# Local variables:
# python-indent: 4
# End:
