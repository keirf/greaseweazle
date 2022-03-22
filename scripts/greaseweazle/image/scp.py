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


# Names for disktype byte in SCP file header
DiskType = {
    'amiga':       0x04,
    'c64':         0x00,
    'atari800-sd': 0x10,
    'atari800-dd': 0x11,
    'atari800-ed': 0x12,
    'atarist-ss':  0x14,
    'atarist-ds':  0x15,
    'appleII':     0x20,
    'appleIIpro':  0x21,
    'apple-400k':  0x24,
    'apple-800k':  0x25,
    'apple-1m44':  0x26,
    'ibmpc-320k':  0x30,
    'ibmpc-720k':  0x31,
    'ibmpc-1m2':   0x32,
    'ibmpc-1m44':  0x33,
    'trs80_sssd':  0x40,
    'trs80_ssdd':  0x41,
    'trs80_dssd':  0x42,
    'trs80_dsdd':  0x43,
    'ti-99/4a':    0x50,
    'roland-d20':  0x60,
    'amstrad-cpc': 0x70,
    'other-320k':  0x80,
    'other-1m2':   0x81,
    'other-720k':  0x84,
    'other-1m44':  0x85,
    'tape-gcr1':   0xe0,
    'tape-gcr2':   0xe1,
    'tape-mfm':    0xe2,
    'hdd-mfm':     0xf0,
    'hdd-rll':     0xf1
}


class SCPOpts:
    """legacy_ss: Set to True to generate (incorrect) legacy single-sided
    SCP image.
    """

    def __init__(self):
        self.legacy_ss = False
        self._disktype = 0x80 # Other

    @property
    def disktype(self):
        return self._disktype
    @disktype.setter
    def disktype(self, disktype):
        try:
            self._disktype = DiskType[disktype.lower()]
        except KeyError:
            try:
                self._disktype = int(disktype, 0)
            except ValueError:
                raise error.Fatal("Bad SCP disktype: '%s'" % disktype)


class SCPTrack:

    def __init__(self, tdh, dat, splice=None):
        self.tdh = tdh
        self.dat = dat
        self.splice = splice


class SCP(Image):

    # 40MHz
    sample_freq = 40000000


    def __init__(self):
        self.opts = SCPOpts()
        self.nr_revs = None
        self.to_track = dict()
        self.index_cued = True

    
    def side_count(self):
        s = [0,0] # non-empty tracks on each side
        for tnr in self.to_track:
            s[tnr&1] += 1
        return s


    @classmethod
    def from_file(cls, name):

        splices = None

        with open(name, "rb") as f:
            dat = f.read()

        header = struct.unpack("<3s9BI", dat[0:16])
        sig, _, disk_type, nr_revs, _, _, flags, _, single_sided, _, _ = header
        error.check(sig == b"SCP", "SCP: Bad signature")

        index_cued = flags & 1 or nr_revs == 1

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

        # Parse the extension block introduced by github:markusC64/g64conv.
        # b'EXTS', length, <length bytes: Extension Area>
        # Extension Area contains consecutive chunks of the form:
        # ID, length, <length bytes: ID-specific data>
        ext_sig, ext_len = None, 0
        if len(dat) >= 0x2b8:
            ext_sig, ext_len = struct.unpack('<4sI', dat[0x2b0:0x2b8])
        min_tdh = min(filter(lambda x: x != 0, trk_offs), default=0)
        if ext_sig == b'EXTS' and 0x2b8 + ext_len <= min_tdh:
            pos, end = 0x2b8, 0x2b8 + ext_len
            while end - pos >= 8:
                chk_sig, chk_len = struct.unpack('<4sI', dat[pos:pos+8])
                pos += 8
                # WRSP: WRite SPlice information block.
                # Data is comprised of >= 169 32-bit values:
                #  0: Flags (currently unused; must be zero)
                #  N: Write splice/overlap position for track N, in SCP ticks
                #     (zero if the track is unused)
                if chk_sig == b'WRSP' and chk_len >= 169*4:
                    # Write-splice positions for writing out SCP tracks
                    # correctly to disk.
                    splices = struct.unpack('<168I', dat[pos+4:pos+169*4])
                pos += chk_len

        scp = cls()

        for trknr in range(len(trk_offs)):
            
            trk_off = trk_offs[trknr]
            if trk_off == 0:
                continue

            # Parse the SCP track header and extract the flux data.
            thdr = dat[trk_off:trk_off+4+12*nr_revs]
            sig, tnr = struct.unpack("<3sB", thdr[:4])
            error.check(sig == b"TRK", "SCP: Missing track signature")
            error.check(tnr == trknr, "SCP: Wrong track number in header")
            thdr = thdr[4:] # Remove TRK header

            # Strip empty trailing revolutions (old versions of FluxEngine).
            while thdr:
                e_ticks, e_nr, e_off = struct.unpack("<3I", thdr[-12:])
                if e_nr != 0 and e_ticks != 0:
                    break
                thdr = thdr[:-12]
            # Bail if all revolutions are empty.
            if not thdr:
                continue

            # Clip the first revolution if it's not flagged as index cued
            # and there's more than one revolution.
            if not index_cued and len(thdr) > 12:
                thdr = thdr[12:]
            s_off, = struct.unpack("<I", thdr[8:12])

            e_off += e_nr*2
            if s_off == e_off:
                # FluxEngine creates dummy TDHs for empty tracks.
                # Bail on them here.
                continue

            tdat = dat[trk_off+s_off:trk_off+e_off]
            track = SCPTrack(thdr, tdat)
            if splices is not None:
                track.splice = splices[trknr]
            scp.to_track[trknr] = track

        s = scp.side_count()

        # C64 images with halftracks are genberated by Supercard Pro using
        # consecutive track numbers. That needs fixup here for our layout.
        # We re-use the legacy-single-sided fixup below.
        if (single_sided == 0 and disk_type == 0
            and s[1] and s[0]==s[1]+1 and s[0] < 42):
            single_sided = 1
            print('SCP: Importing C64 image with halftracks')

        # Some tools produce (or used to produce) single-sided images using
        # consecutive entries in the TLUT. This needs fixing up.
        if single_sided and s[0] and s[1]:
            new_dict = dict()
            for tnr in scp.to_track:
                new_dict[tnr*2+single_sided-1] = scp.to_track[tnr]
            scp.to_track = new_dict
            print('SCP: Imported legacy single-sided image')

        return scp


    def get_track(self, cyl, side):
        tracknr = cyl * 2 + side
        if not tracknr in self.to_track:
            return None
        track = self.to_track[tracknr]
        tdh, dat = track.tdh, track.dat

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

        flux = Flux(index_list, flux_list, SCP.sample_freq)
        flux.splice = track.splice if track.splice is not None else 0
        return flux


    def emit_track(self, cyl, side, track):
        """Converts @track into a Supercard Pro Track and appends it to
        the current image-in-progress.
        """

        flux = track.flux()

        # External tools and emulators generally seem to work best (or only)
        # with index-cued SCP image files. So let's make sure we give them
        # what they want.
        flux.cue_at_index()

        if not flux.index_cued:
            self.index_cued = False

        nr_revs = len(flux.index_list)
        if not self.nr_revs:
            self.nr_revs = nr_revs
        else:
            self.nr_revs = min(self.nr_revs, nr_revs)

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
                                   round(flux.index_list[rev]*factor),
                                   (len(dat) - len_at_index) // 2,
                                   4 + nr_revs*12 + len_at_index)
                # Set up for the next revolution
                len_at_index = len(dat)
                rev += 1
                if rev >= nr_revs:
                    # We're done: We simply discard any surplus flux samples
                    self.to_track[cyl*2+side] = SCPTrack(tdh, dat)
                    return
                to_index += flux.index_list[rev]

            # Process the current flux sample into SCP "bitcell" format
            to_index -= x
            y = x * factor + rem
            val = round(y)
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
                               round(flux.index_list[rev]*factor),
                               (len(dat) - len_at_index) // 2,
                               4 + nr_revs*12 + len_at_index)
            len_at_index = len(dat)
            rev += 1

        self.to_track[cyl*2+side] = SCPTrack(tdh, dat)


    def get_image(self):

        # Work out the single-sided byte code
        s = self.side_count()
        if s[0] and s[1]:
            single_sided = 0
        elif s[0]:
            single_sided = 1
        else:
            single_sided = 2

        to_track = self.to_track
        if single_sided and self.opts.legacy_ss:
            print('SCP: Generated legacy single-sided image')
            to_track = dict()
            for tnr in self.to_track:
                to_track[tnr//2] = self.to_track[tnr]

        ntracks = max(to_track, default=0) + 1

        # Generate the TLUT and concatenate all the tracks together.
        trk_offs = bytearray()
        trk_dat = bytearray()
        for tnr in range(ntracks):
            if tnr in to_track:
                track = to_track[tnr]
                trk_offs += struct.pack("<I", 0x2b0 + len(trk_dat))
                trk_dat += struct.pack("<3sB", b"TRK", tnr)
                trk_dat += track.tdh + track.dat
            else:
                trk_offs += struct.pack("<I", 0)
        error.check(len(trk_offs) <= 0x2a0, "SCP: Too many tracks")
        trk_offs += bytes(0x2a0 - len(trk_offs))

        # Calculate checksum over all data (except 16-byte image header).
        csum = 0
        for x in trk_offs:
            csum += x
        for x in trk_dat:
            csum += x

        # Generate the image header.
        flags = 2 # 96TPI
        if self.index_cued:
            flags |= 1 # Index-Cued
        nr_revs = self.nr_revs if self.nr_revs is not None else 0
        header = struct.pack("<3s9BI",
                             b"SCP",    # Signature
                             0,         # Version
                             self.opts.disktype,
                             nr_revs, 0, ntracks-1,
                             flags,
                             0,         # 16-bit cell width
                             single_sided,
                             0,         # 25ns capture
                             csum & 0xffffffff)

        # Concatenate it all together and send it back.
        return header + trk_offs + trk_dat


# Local variables:
# python-indent: 4
# End:
