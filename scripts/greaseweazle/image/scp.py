# greaseweazle/image/scp.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import struct, functools

from greaseweazle import error
from greaseweazle.flux import Flux
from .image import Image

class SCPOpts:
    """legacy_ss: Set to True to generate (incorrect) legacy single-sided
    SCP image.
    """
    def __init__(self):
        self.legacy_ss = False

class SCP(Image):

    # 40MHz
    sample_freq = 40000000

    def __init__(self, start_cyl, nr_sides):
        self.opts = SCPOpts()
        self.nr_sides = nr_sides
        self.nr_revs = None
        self.track_list = [(None,None)] * (start_cyl*2)


    @classmethod
    def from_file(cls, name):

        with open(name, "rb") as f:
            dat = f.read()

        header = struct.unpack("<3s9BI", dat[0:16])
        (sig, _, _, nr_revs, _, _, flags, _, single_sided, _, _) = header
        error.check(sig == b"SCP", "SCP: Bad signature")

        index_cued = flags & 1 or nr_revs == 1
        if not index_cued:
            nr_revs -= 1
        
        # Some tools generate a short TLUT. We handle this by truncating the
        # TLUT at the first Track Data Header.
        trk_offs = struct.unpack("<168I", dat[16:0x2b0])
        for i in range(168):
            try:
                off = trk_offs[i]
            except IndexError:
                break
            if off == 0 or off >= 0x2b0:
                continue
            off = off//4 - 4
            error.check(off >= 0, "SCP: Bad Track Table")
            trk_offs = trk_offs[:off]

        scp = cls(0, 2)
        scp.nr_revs = nr_revs

        for trknr in range(len(trk_offs)):
            
            trk_off = trk_offs[trknr]
            if trk_off == 0:
                scp.track_list.append((None, None))
                continue

            # Parse the SCP track header and extract the flux data.
            thdr = dat[trk_off:trk_off+4+12*nr_revs]
            sig, tnr = struct.unpack("<3sB", thdr[:4])
            error.check(sig == b"TRK", "SCP: Missing track signature")
            error.check(tnr == trknr, "SCP: Wrong track number in header")
            _off = 12 if index_cued else 24 # skip first partial rev
            s_off, = struct.unpack("<I", thdr[_off:_off+4])
            _, e_nr, e_off = struct.unpack("<3I", thdr[-12:])

            e_off += e_nr*2
            if s_off == e_off:
                # FluxEngine creates dummy TDHs for empty tracks.
                # Bail on them here.
                scp.track_list.append((None, None))
                continue
                
            tdat = dat[trk_off+s_off:trk_off+e_off]
            scp.track_list.append((thdr[4:], tdat))

        # s[side] is True iff there are non-empty tracks on @side
        s = []
        for i in range(2):
            s.append(functools.reduce(lambda x, y: x or (y[1] is not None),
                                      scp.track_list[i::2], False))
            
        # Some tools produce (or used to produce) single-sided images using
        # consecutive entries in the TLUT. This needs fixing up.
        if single_sided and functools.reduce(lambda x, y: x and y, s):
            new_list = []
            for t in scp.track_list[:84]:
                if single_sided != 1: # Side 1
                    new_list.append((None, None))
                new_list.append(t)
                if single_sided == 1: # Side 0
                    new_list.append((None, None))
            scp.track_list = new_list
            print('SCP: Imported legacy single-sided image')
            
        return scp


    def get_track(self, cyl, side):
        off = cyl*2 + side
        if off >= len(self.track_list):
            return None
        tdh, dat = self.track_list[off]
        if dat is None:
            return None

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


    def append_track(self, track):
        """Converts @track into a Supercard Pro Track and appends it to
        the current image-in-progress.
        """

        def _append(self, tdh, dat):
            self.track_list.append((tdh, dat))
            if self.nr_sides == 1:
                self.track_list.append((None, None))

        flux = track.flux()

        nr_revs = len(flux.index_list)
        if not self.nr_revs:
            self.nr_revs = nr_revs
        else:
            assert self.nr_revs == nr_revs
        
        factor = SCP.sample_freq / flux.sample_freq

        tdh, dat = bytearray(), bytearray()
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
                    _append(self, tdh, dat)
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

        _append(self, tdh, dat)


    def get_image(self):
        single_sided = 1 if self.nr_sides == 1 else 0
        track_list = self.track_list
        if single_sided and self.opts.legacy_ss:
            print('SCP: Generated legacy single-sided image')
            track_list = track_list[::2]
        # Generate the TLUT and concatenate all the tracks together.
        trk_offs = bytearray()
        trk_dat = bytearray()
        for trknr in range(len(track_list)):
            tdh, dat = track_list[trknr]
            if dat is None:
                trk_offs += struct.pack("<I", 0)
            else:
                trk_offs += struct.pack("<I", 0x2b0 + len(trk_dat))
                trk_dat += struct.pack("<3sB", b"TRK", trknr) + tdh + dat
        error.check(len(trk_offs) <= 0x2a0, "SCP: Too many tracks")
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
                             self.nr_revs, 0, len(track_list) - 1,
                             0x03,      # Flags = Index, 96TPI
                             0,         # 16-bit cell width
                             single_sided,
                             0,         # 25ns capture
                             csum & 0xffffffff)
        # Concatenate it all together and send it back.
        return header + trk_offs + trk_dat


# Local variables:
# python-indent: 4
# End:
