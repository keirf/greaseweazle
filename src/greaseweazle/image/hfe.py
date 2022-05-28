# greaseweazle/image/hfe.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import struct

from greaseweazle import error
from greaseweazle.track import MasterTrack, RawTrack
from bitarray import bitarray
from .image import Image

class HFEOpts:
    """bitrate: Bitrate of new HFE image file.
    """
    
    def __init__(self):
        self._bitrate = None

    @property
    def bitrate(self):
        return self._bitrate
    @bitrate.setter
    def bitrate(self, bitrate):
        try:
            self._bitrate = int(bitrate)
            if self._bitrate <= 0:
                raise ValueError
        except ValueError:
            raise error.Fatal("HFE: Invalid bitrate: '%s'" % bitrate)


class HFE(Image):

    def __init__(self):
        self.opts = HFEOpts()
        # Each track is (bitlen, rawbytes).
        # rawbytes is a bytes() object in little-endian bit order.
        self.to_track = dict()


    @classmethod
    def from_file(cls, name):

        with open(name, "rb") as f:
            dat = f.read()

        (sig, f_rev, n_cyl, n_side, t_enc, bitrate,
         _, _, _, tlut_base) = struct.unpack("<8s4B2H2BH", dat[:20])
        error.check(sig != b"HXCHFEV3", "HFEv3 is not supported")
        error.check(sig == b"HXCPICFE" and f_rev <= 1, "Not a valid HFE file")
        error.check(0 < n_cyl, "HFE: Invalid #cyls")
        error.check(0 < n_side < 3, "HFE: Invalid #sides")

        hfe = cls()
        hfe.opts.bitrate = bitrate

        tlut = dat[tlut_base*512:tlut_base*512+n_cyl*4]
        
        for cyl in range(n_cyl):
            for side in range(n_side):
                offset, length = struct.unpack("<2H", tlut[cyl*4:(cyl+1)*4])
                todo = length // 2
                tdat = bytes()
                while todo:
                    d_off = offset*512 + side*256
                    d_nr = 256 if todo > 256 else todo
                    tdat += dat[d_off:d_off+d_nr]
                    todo -= d_nr
                    offset += 1
                hfe.to_track[cyl,side] = (len(tdat)*8, tdat)

        return hfe


    def get_track(self, cyl, side):
        if (cyl,side) not in self.to_track:
            return None
        bitlen, rawbytes = self.to_track[cyl,side]
        tdat = bitarray(endian='little')
        tdat.frombytes(rawbytes)
        track = MasterTrack(
            bits = tdat[:bitlen],
            time_per_rev = bitlen / (2000*self.opts.bitrate))
        return track


    def emit_track(self, cyl, side, track):
        if self.opts.bitrate is None:
            t = track.raw_track() if hasattr(track, 'raw_track') else track
            b = getattr(t, 'bitrate', None)
            error.check(hasattr(t, 'bitrate'),
                        'HFE: Requires bitrate to be specified'
                        ' (eg. filename.hfe::bitrate=500)')
            self.opts.bitrate = round(t.bitrate / 2e3)
            print('HFE: Data bitrate detected: %d kbit/s' % self.opts.bitrate)
        flux = track.flux()
        flux.cue_at_index()
        raw = RawTrack(clock = 5e-4 / self.opts.bitrate, data = flux)
        bits, _ = raw.get_revolution(0)
        bits.bytereverse()
        self.to_track[cyl,side] = (len(bits), bits.tobytes())


    def get_image(self):

        n_side = 1
        n_cyl = max(self.to_track.keys(), default=(0,), key=lambda x:x[0])[0]
        n_cyl += 1

        # We dynamically build the Track-LUT and -Data arrays.
        tlut = bytearray()
        tdat = bytearray()

        # Stuff real data into the image.
        for i in range(n_cyl):
            s0 = self.to_track[i,0] if (i,0) in self.to_track else None
            s1 = self.to_track[i,1] if (i,1) in self.to_track else None
            if s0 is None and s1 is None:
                # Dummy data for empty cylinders. Assumes 300RPM.
                nr_bytes = 100 * self.opts.bitrate
                tlut += struct.pack("<2H", len(tdat)//512 + 2, nr_bytes)
                tdat += bytes([0x88] * (nr_bytes+0x1ff & ~0x1ff))
            else:
                # At least one side of this cylinder is populated.
                if s1 is not None:
                    n_side = 2
                bc = [s0 if s0 is not None else (0,bytes()),
                      s1 if s1 is not None else (0,bytes())]
                nr_bytes = max(len(t[1]) for t in bc)
                nr_blocks = (nr_bytes + 0xff) // 0x100
                tlut += struct.pack("<2H", len(tdat)//512 + 2, 2 * nr_bytes)
                for b in range(nr_blocks):
                    for t in bc:
                        slice = t[1][b*256:(b+1)*256]
                        tdat += slice + bytes([0x88] * (256 - len(slice)))

        # Construct the image header.
        header = struct.pack("<8s4B2H2BH",
                             b"HXCPICFE",
                             0,
                             n_cyl,
                             n_side,
                             0xff, # unknown encoding
                             self.opts.bitrate,
                             0,    # rpm (unused)
                             0xff, # unknown interface
                             1,    # rsvd
                             1)    # track list offset

        # Pad the header and TLUT to 512-byte blocks.
        header += bytes([0xff] * (0x200 - len(header)))
        tlut += bytes([0xff] * (0x200 - len(tlut)))

        return header + tlut + tdat


# Local variables:
# python-indent: 4
# End:
