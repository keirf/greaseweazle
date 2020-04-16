# greaseweazle/image/hfe.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import struct

from greaseweazle.flux import Flux
from greaseweazle.bitcell import Bitcell
from bitarray import bitarray

class HFE:

    def __init__(self, start_cyl, nr_sides):
        self.start_cyl = start_cyl
        self.nr_sides = nr_sides
        self.bitrate = 250 # XXX real bitrate?
        # Each track is (bitlen, rawbytes).
        # rawbytes is a bytes() object in little-endian bit order.
        self.track_list = []


    @classmethod
    def to_file(cls, start_cyl, nr_sides):
        hfe = cls(start_cyl, nr_sides)
        return hfe


    @classmethod
    def from_file(cls, dat):

        (sig, f_rev, nr_cyls, nr_sides, t_enc, bitrate,
         _, _, _, tlut_base) = struct.unpack("<8s4B2H2BH", dat[:20])
        assert sig != b"HXCHFEV3", "HFEv3 is not supported"
        assert sig == b"HXCPICFE" and f_rev <= 1, "Not a valid HFE file"
        assert 0 < nr_cyls
        assert 0 < nr_sides < 3
        assert bitrate != 0
        
        hfe = cls(0, nr_sides)
        hfe.bitrate = bitrate

        tlut = dat[tlut_base*512:tlut_base*512+nr_cyls*4]
        
        for cyl in range(nr_cyls):
            for side in range(nr_sides):
                offset, length = struct.unpack("<2H", tlut[cyl*4:(cyl+1)*4])
                todo = length // 2
                tdat = bytes()
                while todo:
                    d_off = offset*512 + side*256
                    d_nr = 256 if todo > 256 else todo
                    tdat += dat[d_off:d_off+d_nr]
                    todo -= d_nr
                    offset += 1
                hfe.track_list.append((len(tdat)*8, tdat))

        return hfe


    def get_track(self, cyl, side, writeout=False):
        if side >= self.nr_sides or cyl < self.start_cyl:
            return None
        off = cyl * self.nr_sides + side
        if off >= len(self.track_list):
            return None
        bitlen, rawbytes = self.track_list[off]
        tdat = bitarray(endian='little')
        tdat.frombytes(rawbytes)
        tdat = tdat[:bitlen]
        return Flux.from_bitarray(tdat, self.bitrate * 2000)


    def append_track(self, flux):
        bc = Bitcell()
        bc.clock = 0.0005 / self.bitrate
        bc.from_flux(flux)
        bits = bc.revolution_list[0][0]
        bits.bytereverse()
        self.track_list.append((len(bits), bits.tobytes()))


    def get_image(self):

        # Construct the image header.
        n_cyl = self.start_cyl + len(self.track_list) // self.nr_sides
        header = struct.pack("<8s4B2H2BH",
                             b"HXCPICFE",
                             0,
                             n_cyl,
                             self.nr_sides,
                             0xff, # unknown encoding
                             self.bitrate,
                             0,    # rpm (unused)
                             0xff, # unknown interface
                             1,    # rsvd
                             1)    # track list offset

        # We dynamically build the Track-LUT and -Data arrays.
        tlut = bytearray()
        tdat = bytearray()

        # Dummy data for unused initial cylinders. Assumes 300RPM.
        for i in range(self.start_cyl):
            nr_bytes = 100 * self.bitrate
            tlut += struct.pack("<2H", len(tdat)//512 + 2, nr_bytes)
            tdat += bytes([0x88] * (nr_bytes+0x1ff & ~0x1ff))

        # Stuff real data into the image.
        for i in range(0, len(self.track_list), self.nr_sides):
            bc = [self.track_list[i],
                  self.track_list[i+1] if self.nr_sides > 1 else (0,bytes())]
            nr_bytes = max(len(t[1]) for t in bc)
            nr_blocks = (nr_bytes + 0xff) // 0x100
            tlut += struct.pack("<2H", len(tdat)//512 + 2, 2 * nr_bytes)
            for b in range(nr_blocks):
                for t in bc:
                    slice = t[1][b*256:(b+1)*256]
                    tdat += slice + bytes([0x88] * (256 - len(slice)))

        # Pad the header and TLUT to 512-byte blocks.
        header += bytes([0xff] * (0x200 - len(header)))
        tlut += bytes([0xff] * (0x200 - len(tlut)))

        return header + tlut + tdat


# Local variables:
# python-indent: 4
# End:
