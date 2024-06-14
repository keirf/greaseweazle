# greaseweazle/image/scp.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from typing import Dict, Tuple, Optional, List

import struct, time
from enum import IntFlag

from greaseweazle import __version__
from greaseweazle import error
from greaseweazle.codec import codec
from greaseweazle.flux import Flux, HasFlux
from greaseweazle.tools import util
from greaseweazle.track import MasterTrack
from .image import Image, ImageOpts

#  SCP image specification can be found at Jim Drew's site:
#  https://www.cbmstuff.com/downloads/scp/scp_image_specs.txt

# Names for disktype byte in SCP file header
DiskType = {
    'c64':         0x00,
    'amiga':       0x04,
    'amigahd':     0x08,
    'atari800-sd': 0x10,
    'atari800-dd': 0x11,
    'atari800-ed': 0x12,
    'atarist-ss':  0x14,
    'atarist-ds':  0x15,
    'appleii':     0x20,
    'appleiipro':  0x21,
    'apple-400k':  0x24,
    'apple-800k':  0x25,
    'apple-1m44':  0x26,
    'ibmpc-360k':  0x30,
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


class SCPHeaderFlags(IntFlag):
    INDEXED       = 1<<0  # image used the index mark to cue tracks
    TPI_96        = 1<<1  # drive is 96 TPI, otherwise 48 TPI
    RPM_360       = 1<<2  # drive is 360RPM, otherwise 300RPM
    NORMALISED    = 1<<3  # flux has been normalized, otherwise is raw
    READWRITE     = 1<<4  # image is read/write capable, otherwise read-only
    FOOTER        = 1<<5  # image contains an extension footer
    EXTENDED_MODE = 1<<6  # image is the extended type for other media
    FLUX_CREATOR  = 1<<7  # image was created by a non SuperCard Pro Device


class SCPOpts(ImageOpts):
    """legacy_ss: Set to True to generate (incorrect) legacy single-sided
    SCP image.
    revs: Number of revolutions to output per track.
    """

    w_settings = [ 'disktype', 'legacy_ss', 'revs' ]

    def __init__(self) -> None:
        self.legacy_ss = False
        self._disktype = 0x80 # Other
        self._revs: Optional[int] = None

    @property
    def disktype(self) -> int:
        return self._disktype
    @disktype.setter
    def disktype(self, disktype):
        try:
            self._disktype = DiskType[disktype.lower()]
        except KeyError:
            try:
                self._disktype = int(disktype, 0)
            except ValueError:
                l = [ x.lower() for x in DiskType.keys() ]
                l.sort()
                raise error.Fatal("Bad SCP disktype: '%s'\n" % disktype
                                  + 'Valid types:\n' + util.columnify(l))

    @property
    def revs(self) -> Optional[int]:
        return self._revs
    @revs.setter
    def revs(self, revs: str) -> None:
        try:
            self._revs = int(revs)
            if self._revs < 1:
                raise ValueError
        except ValueError:
            raise error.Fatal("Kryoflux: Invalid revs: '%s'" % revs)


class SCPTrack:

    def __init__(self, tdh, dat, splice=None):
        self.tdh = tdh
        self.dat = dat
        self.splice = splice


class SCP(Image):

    # 40MHz
    sample_freq = 40000000
    opts: SCPOpts


    def __init__(self, name: str, _fmt) -> None:
        self.opts = SCPOpts()
        self.nr_revs: Optional[int] = None
        self.to_track: Dict[int, SCPTrack] = dict()
        self.index_cued = True
        self.filename = name


    def side_count(self) -> List[int]:
        s = [0,0] # non-empty tracks on each side
        for tnr in self.to_track:
            s[tnr&1] += 1
        return s


    def from_bytes(self, dat: bytes) -> None:

        splices = None

        (sig, _, disk_type, nr_revs, _, _, flags, _, single_sided, _,
         checksum) = struct.unpack("<3s9BI", dat[0:16])
        error.check(sig == b"SCP", "SCP: Bad signature")

        if sum(dat[16:]) & 0xffffffff != checksum:
            print('SCP: WARNING: Bad image checksum')

        index_cued = (flags & 1) == 1 or nr_revs == 1

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
            self.to_track[trknr] = track

        s = self.side_count()

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
            for tnr in self.to_track:
                new_dict[tnr*2+single_sided-1] = self.to_track[tnr]
            self.to_track = new_dict
            print('SCP: Imported legacy single-sided image')


    def get_track(self, cyl: int, side: int) -> Optional[Flux]:
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
        flux.splice = track.splice
        return flux


    def emit_track(self, cyl: int, side: int, track: HasFlux) -> None:
        """Converts @track into a Supercard Pro Track and appends it to
        the current image-in-progress.
        """

        if isinstance(track, codec.Codec):
            track = track.master_track()
        if isinstance(track, MasterTrack):
            # Get a consistent number of revolutions, allowing for data
            # across the index mark (which ideally warrants two revolutions).
            mt_revs = 2 if self.opts.revs is None else self.opts.revs
            flux = track.flux(revs = mt_revs)
        else:
            flux = track.flux()

        # External tools and emulators generally seem to work best (or only)
        # with index-cued SCP image files. So let's make sure we give them
        # what they want.
        flux.cue_at_index()

        if self.opts.revs is not None:
            flux.set_nr_revs(self.opts.revs)

        if not flux.index_cued:
            self.index_cued = False

        nr_revs = len(flux.index_list)
        if not self.nr_revs:
            self.nr_revs = nr_revs
        else:
            self.nr_revs = min(self.nr_revs, nr_revs)

        factor = SCP.sample_freq / flux.sample_freq
        splice = None if flux.splice is None else round(flux.splice * factor)

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
                    self.to_track[cyl*2+side] = SCPTrack(tdh, dat, splice)
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

        self.to_track[cyl*2+side] = SCPTrack(tdh, dat, splice)


    def get_image(self) -> bytes:

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

        # Emit a WRSP block iff we have at least one known splice point.
        emit_wrsp = False
        for track in to_track.values():
            if track.splice is not None:
                emit_wrsp = True
        wrsp, wrsp_len = bytearray(), 0
        if emit_wrsp:
            wrsp_len = (2+2+169)*4
            wrsp += struct.pack('<4sI4s2I',
                                b'EXTS', wrsp_len- 8,  # EXTS header
                                b'WRSP', wrsp_len-16,  # WRSP header
                                0)                     # WRSP flags field

        # Generate the TLUT and concatenate all the tracks together.
        trk_offs, trk_offs_len = bytearray(), 0x2a0
        trk_dat = bytearray()
        trk_start = 0x10 + trk_offs_len + wrsp_len
        for tnr in range(ntracks):
            if tnr in to_track:
                track = to_track[tnr]
                trk_offs += struct.pack("<I", trk_start + len(trk_dat))
                trk_dat += struct.pack("<3sB", b"TRK", tnr)
                trk_dat += track.tdh + track.dat
                splice = 0 if track.splice is None else track.splice
            else:
                trk_offs += struct.pack("<I", 0)
                splice = 0
            if emit_wrsp:
                wrsp += struct.pack("<I", splice)
        error.check(len(trk_offs) <= trk_offs_len, "SCP: Too many tracks")
        trk_offs += bytes(trk_offs_len - len(trk_offs))
        wrsp += bytes(wrsp_len - len(wrsp))

        creation_time = round(time.time())
        footer_offs = trk_start + len(trk_dat)
        app_name = f'Greaseweazle {__version__}'.encode()
        footer = struct.pack('<H', len(app_name)) + app_name + b'\0'
        footer += struct.pack('<6I2Q4B4s',
                              0, # drive manufacturer
                              0, # drive model
                              0, # drive serial
                              0, # creator name
                              footer_offs, # application name
                              0, # comments
                              creation_time, # creation time
                              creation_time, # modification time
                              0, # application version
                              0, # hardware version
                              0, # firmware version
                              0x24, # format version (v2.4)
                              b'FPCS')

        # Concatenate all data together for checksumming.
        data = trk_offs + wrsp + trk_dat + footer

        # Generate the image header.
        flags = SCPHeaderFlags.TPI_96 | SCPHeaderFlags.FOOTER
        if self.index_cued:
            flags |= SCPHeaderFlags.INDEXED
        nr_revs = self.nr_revs if self.nr_revs is not None else 0
        header = struct.pack("<3s9BI",
                             b"SCP",    # Signature
                             0,
                             self.opts.disktype,
                             nr_revs,
                             0,         # start track
                             ntracks-1, # end track
                             flags,
                             0,         # 16-bit cell width
                             single_sided,
                             0,         # 25ns capture
                             sum(data) & 0xffffffff)

        # Concatenate it all together and send it back.
        return header + data


# Local variables:
# python-indent: 4
# End:
