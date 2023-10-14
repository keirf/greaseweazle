# greaseweazle/tools/write.py
#
# Greaseweazle control script: Write Image to Disk.
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

description = "Write a disk from the specified image file."

from typing import cast, Optional, List, Type

import sys, copy

from greaseweazle.tools import util
from greaseweazle import error, track
from greaseweazle import usb as USB
from greaseweazle.codec import codec
from greaseweazle.image import image
from greaseweazle.track import HasVerify, MasterTrack

# Read and parse the image file.
def open_image(args, image_class: Type[image.Image]) -> image.Image:
    return image_class.from_file(args.file, args.fmt_cls, args.file_opts)

# write_from_image:
# Writes the specified image file to floppy disk.
def write_from_image(usb: USB.Unit, args, image: image.Image) -> None:

    # Measure drive RPM.
    # We will adjust the flux intervals per track to allow for this.
    no_index = args.fake_index is not None
    if no_index:
        drive_ticks_per_rev = args.fake_index * usb.sample_freq
    else:
        drive_ticks_per_rev = usb.read_track(2).ticks_per_rev

    verified_count, not_verified_count = 0, 0

    for t in args.tracks:

        cyl, head = t.cyl, t.head

        track = image.get_track(cyl, head)
        if track is None and not args.erase_empty:
            continue

        usb.seek(t.physical_cyl, t.physical_head)

        if track is None:
            print("T%u.%u: Erasing Track" % (cyl, head))
            usb.erase_track(drive_ticks_per_rev * 1.1)
            continue

        if not isinstance(track, codec.Codec) and args.fmt_cls is not None:
            track = args.fmt_cls.decode_flux(cyl, head, track)
            if track is None:
                print("T%u.%u: WARNING: out of range for format '%s': Track "
                      "skipped" % (cyl, head, args.format))
                continue
            assert isinstance(track, codec.Codec)
            error.check(track.nr_missing() == 0,
                        'T%u.%u: %u missing sectors in input image'
                        % (cyl, head, track.nr_missing()))
        if isinstance(track, codec.Codec):
            track = track.master_track()

        if args.precomp is not None and isinstance(track, MasterTrack):
            track.precomp = args.precomp.track_precomp(cyl)
        wflux = track.flux_for_writeout(cue_at_index = not no_index)

        # @factor adjusts flux times for speed variations between the
        # read-in and write-out drives.
        factor = drive_ticks_per_rev / wflux.ticks_to_index

        # Convert the flux samples to Greaseweazle sample frequency.
        rem = 0.0
        wflux_list = []
        for x in wflux.list:
            y = x * factor + rem
            val = round(y)
            rem = y - val
            wflux_list.append(val)

        # Encode the flux times for Greaseweazle, and write them out.
        verified = False
        for retry in range(args.retries+1):
            if args.pre_erase:
                print("T%u.%u: Erasing Track" % (cyl, head))
                usb.erase_track(drive_ticks_per_rev * 1.1)
            s = "T%u.%u: Writing Track" % (cyl, head)
            if retry != 0:
                s += " (Verify Failure: Retry #%u)" % retry
            else:
                s += " (%s)" % wflux.summary_string()
            print(s)
            usb.write_track(flux_list = wflux_list,
                            cue_at_index = wflux.index_cued,
                            terminate_at_index = wflux.terminate_at_index)
            verify: Optional[HasVerify] = None
            no_verify = (args.no_verify
                         or not isinstance(track, MasterTrack)
                         or (verify := track.verify) is None)
            if no_verify:
                not_verified_count += 1
                verified = True
                break
            assert verify is not None # mypy
            v_revs, v_ticks = verify.verify_revs, 0
            if isinstance(v_revs, float):
                v_ticks = int(drive_ticks_per_rev * v_revs)
                v_revs = 2
            if no_index:
                drive_tpr = int(drive_ticks_per_rev)
                pre_index = int(usb.sample_freq * 0.5e-3)
                if v_ticks == 0:
                    v_ticks = v_revs*drive_tpr + 2*pre_index
                v_flux = usb.read_track(revs = 0, ticks = v_ticks)
                index_list = (
                    [pre_index]
                    + [drive_tpr] * ((v_ticks-pre_index)//drive_tpr))
                v_flux.index_list = cast(List[float], index_list) # mypy
            else:
                v_flux = usb.read_track(revs = v_revs, ticks = v_ticks)
            v_flux._ticks_per_rev = drive_ticks_per_rev
            verified = verify.verify_track(v_flux)
            if verified:
                verified_count += 1
                break
        error.check(verified, "Failed to verify Track %u.%u" % (cyl, head))

    if not_verified_count == 0:
        print("All tracks verified")
    else:
        if verified_count == 0:
            s = "No tracks verified "
        else:
            s = ("%d tracks verified; %d tracks *not* verified "
                 % (verified_count, not_verified_count))
        s += ("(Reason: Verify %s)"
              % ("unavailable", "disabled")[args.no_verify])
        print(s)


class PrecompSpec:
    def __str__(self) -> str:
        s = "Precomp %s" % track.Precomp.TYPESTRING[self.type]
        for e in self.list:
            s += ", %d-:%dns" % e
        return s

    def track_precomp(self, cyl: int) -> Optional[track.Precomp]:
        for c,s in reversed(self.list):
            if cyl >= c:
                return track.Precomp(self.type, s)
        return None

    def importspec(self, spec: str) -> None:
        self.list = []
        self.type = track.Precomp.MFM
        for x in spec.split(':'):
            k,v = x.split('=')
            if k == 'type':
                self.type = track.Precomp.TYPESTRING.index(v.upper())
            else:
                self.list.append((int(k), int(v)))
        self.list.sort()

    def __init__(self, spec: str) -> None:
        try:
            self.importspec(spec)
        except:
            raise ValueError
        

def main(argv) -> None:

    epilog = (util.drive_desc + "\n"
              + util.speed_desc + "\n" + util.tspec_desc
              + "\nFORMAT options:\n" + codec.print_formats()
              + "\n\nSupported file suffixes:\n"
              + util.columnify(util.image_types))
    parser = util.ArgumentParser(usage='%(prog)s [options] file',
                                 epilog=epilog)
    parser.add_argument("--device", help="device name (COM/serial port)")
    parser.add_argument("--drive", type=util.Drive(), default='A',
                        help="drive to read")
    parser.add_argument("--diskdefs", help="disk definitions file")
    parser.add_argument("--format", help="disk format")
    parser.add_argument("--tracks", type=util.TrackSet, metavar="TSPEC",
                        help="which tracks to write")
    parser.add_argument("--pre-erase", action="store_true",
                        help="erase tracks before writing (default: no)")
    parser.add_argument("--erase-empty", action="store_true",
                        help="erase empty tracks (default: skip)")
    parser.add_argument("--fake-index", type=util.period, metavar="SPEED",
                        help="fake index pulses at SPEED")
    parser.add_argument("--no-verify", action="store_true",
                        help="disable verify")
    parser.add_argument("--retries", type=util.uint, default=3, metavar="N",
                        help="number of retries on verify failure")
    parser.add_argument("--precomp", type=PrecompSpec,
                        help="write precompensation")
    parser.add_argument("--dd", type=util.level,
                        help="drive interface DD/HD select (H,L)")
    parser.add_argument("file", help="input filename")
    parser.description = description
    parser.prog += ' ' + argv[1]
    args = parser.parse_args(argv[2:])

    args.file, args.file_opts = util.split_opts(args.file)

    try:
        image_class = util.get_image_class(args.file)
        if not args.format:
            args.format = image_class.default_format
        def_tracks, args.fmt_cls = None, None
        if args.format:
            args.fmt_cls = codec.get_diskdef(args.format, args.diskdefs)
            if args.fmt_cls is None:
                raise error.Fatal("""\
Unknown format '%s'
Known formats:\n%s"""
                                  % (args.format, codec.print_formats(
                                      args.diskdefs)))
            def_tracks = copy.copy(args.fmt_cls.tracks)
        if def_tracks is None:
            def_tracks = util.TrackSet('c=0-81:h=0-1')
        if args.tracks is not None:
            def_tracks.update_from_trackspec(args.tracks.trackspec)
        args.tracks = def_tracks
        usb = util.usb_open(args.device)
        image = open_image(args, image_class)
        print("Writing " + str(args.tracks))
        if args.precomp is not None:
            print(args.precomp)
        if hasattr(image, 'format_str'):
            print("Image format " + image.format_str)
            error.check(args.format is None,
                        'Cannot override image format with --format')
        if args.format:
            print("Format " + args.format)
        try:
            if args.dd is not None:
                prev_pin2 = usb.get_pin(2)
                usb.set_pin(2, args.dd)
            util.with_drive_selected(
                lambda: write_from_image(usb, args, image), usb, args.drive)
        finally:
            if args.dd is not None:
                usb.set_pin(2, prev_pin2)
    except USB.CmdError as err:
        print("Command Failed: %s" % err)


if __name__ == "__main__":
    main(sys.argv)

# Local variables:
# python-indent: 4
# End:
