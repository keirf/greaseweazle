# greaseweazle/image/scp.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import struct

from greaseweazle.flux import Flux

class SCP:

    # 40MHz
    sample_freq = 40000000

    def __init__(self, start_cyl, nr_sides):
        self.start_cyl = start_cyl
        self.nr_sides = nr_sides
        self.nr_revs = None
        self.track_list = []


    @classmethod
    def to_file(cls, start_cyl, nr_sides):
        hfe = cls(start_cyl, nr_sides)
        return hfe


    @classmethod
    def from_file(cls, dat):

        header = struct.unpack("<3s9BI", dat[0:16])
        (sig, _, _, nr_revs, s_trk, e_trk, flags, _, ss, _, _) = header
        assert sig == b"SCP"
        nr_sides = 1 if ss else 2
        
        trk_offs = struct.unpack("<168I", dat[16:0x2b0])

        scp = cls(s_trk // nr_sides, nr_sides)
        scp.nr_revs = nr_revs

        for trknr in range(s_trk, e_trk+1):
            trk_off = trk_offs[trknr]
            if trk_off == 0:
                scp.track_list.append((None, None))

            # Parse the SCP track header and extract the flux data.
            thdr = dat[trk_off:trk_off+4+12*nr_revs]
            sig, tnr, _, _, s_off = struct.unpack("<3sB3I", thdr[:16])
            assert sig == b"TRK"
            assert tnr == trknr
            _, e_nr, e_off = struct.unpack("<3I", thdr[-12:])
            tdat = dat[trk_off+s_off:trk_off+e_off+e_nr*2]

            scp.track_list.append((thdr, tdat))

        return scp


    def get_track(self, cyl, side, writeout=False):
        if side >= self.nr_sides or cyl < self.start_cyl:
            return None
        off = (cyl - self.start_cyl) * self.nr_sides + side
        if off >= len(self.track_list):
            return None
        tdh, dat = self.track_list[off]
        if not dat:
            return None
        tdh = tdh[4:]

        # Writeout requires only a single revolution
        if writeout:
            tdh = tdh[:12]
            _, nr, _ = struct.unpack("<3I", tdh)
            dat = dat[:nr*2]
        
        index_list = []
        while tdh:
            ticks, _, _ = struct.unpack("<3I", tdh[:12])
            index_list.append(ticks)
            tdh = tdh[12:]
        
        # Decode the SCP flux data into a simple list of flux times.
        flux_list = []
        val = 0
        for i in range(0, len(dat), 2):
            x = dat[i]*256 + dat[i+1]
            if x == 0:
                val += 65536
                continue
            flux_list.append(val + x)
            val = 0

        return Flux(index_list, flux_list, SCP.sample_freq)
    
        
    # append_track:
    # Converts a Flux object into a Supercard Pro Track and appends it to
    # the current image-in-progress.
    def append_track(self, flux):

        nr_revs = len(flux.index_list)
        if not self.nr_revs:
            self.nr_revs = nr_revs
        else:
            assert self.nr_revs == nr_revs
        
        factor = SCP.sample_freq / flux.sample_freq

        trknr = self.start_cyl * self.nr_sides + len(self.track_list)
        tdh = struct.pack("<3sB", b"TRK", trknr)
        dat = bytearray()

        len_at_index = rev = 0
        to_index = flux.index_list[0]
        rem = 0.0

        for x in flux.list:

            # Does the next flux interval cross the index mark?
            while to_index < x:
                # Append to the TDH for the previous full revolution
                tdh += struct.pack("<III",
                                   int(round(flux.index_list[rev]*factor)),
                                   (len(dat) - len_at_index) // 2,
                                   4 + nr_revs*12 + len_at_index)
                # Set up for the next revolution
                len_at_index = len(dat)
                rev += 1
                if rev >= nr_revs:
                    # We're done: We simply discard any surplus flux samples
                    self.track_list.append((tdh, dat))
                    return
                to_index += flux.index_list[rev]

            # Process the current flux sample into SCP "bitcell" format
            to_index -= x
            y = x * factor + rem
            val = int(round(y))
            if (val & 65535) == 0:
                val += 1
            rem = y - val
            while val >= 65536:
                dat.append(0)
                dat.append(0)
                val -= 65536
            dat.append(val>>8)
            dat.append(val&255)

        # Header for last track(s) in case we ran out of flux timings.
        while rev < nr_revs:
            tdh += struct.pack("<III",
                               int(round(flux.index_list[rev]*factor)),
                               (len(dat) - len_at_index) // 2,
                               4 + nr_revs*12 + len_at_index)
            len_at_index = len(dat)
            rev += 1

        self.track_list.append((tdh, dat))


    def get_image(self):
        s_trk = self.start_cyl * self.nr_sides
        e_trk = s_trk + len(self.track_list) - 1
        # Generate the TLUT and concatenate all the tracks together.
        trk_offs = bytearray(s_trk * 4)
        trk_dat = bytearray()
        for tdh, dat in self.track_list:
            trk_offs += struct.pack("<I", 0x2b0 + len(trk_dat))
            trk_dat += tdh + dat
        trk_offs += bytes(0x2a0 - len(trk_offs))
        # Calculate checksum over all data (except 16-byte image header).
        csum = 0
        for x in trk_offs:
            csum += x
        for x in trk_dat:
            csum += x
        # Generate the image header.
        header = struct.pack("<3s9BI",
                             b"SCP",    # Signature
                             0,         # Version
                             0x80,      # DiskType = Other
                             self.nr_revs, s_trk, e_trk,
                             0x01,      # Flags = Index
                             0,         # 16-bit cell width
                             1 if self.nr_sides == 1 else 0,
                             0,         # 25ns capture
                             csum & 0xffffffff)
        # Concatenate it all together and send it back.
        return header + trk_offs + trk_dat


# Local variables:
# python-indent: 4
# End:
