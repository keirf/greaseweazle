# greaseweazle/scp.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import struct

class SCP:

    # 40MHz
    sample_freq = 40000000

    def __init__(self, start_cyl, nr_sides):
        self.start_cyl = start_cyl
        self.nr_sides = nr_sides
        self.nr_revs = None
        self.track_list = []

    # append_track:
    # Converts a Flux object into a Supercard Pro Track and appends it to
    # the current image-in-progress.
    def append_track(self, flux):

        nr_revs = len(flux.index_list) - 1
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

            # Are we processing initial samples before the first revolution?
            if rev == 0:
                if to_index >= x:
                    # Discard initial samples
                    to_index -= x
                    continue
                # Now starting the first full revolution
                rev = 1
                to_index += flux.index_list[rev]

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
                if rev > nr_revs:
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
        while rev <= nr_revs:
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
