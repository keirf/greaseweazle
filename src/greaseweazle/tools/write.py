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
from greaseweazle.image.img import IMG
from greaseweazle.track import HasVerify, MasterTrack

# Read and parse the image file.
def open_image(args, image_class: Type[image.Image]) -> image.Image:
    return image_class.from_file(args.file, args.fmt_cls, args.file_opts)

# write_from_image:
# Writes the specified image file to floppy disk.
def write_from_image(usb: USB.Unit, args, image: image.Image) -> None:

    hard_sector_ticks = 0

    # Measure drive RPM.
    # We will adjust the flux intervals per track to allow for this.
    no_index = args.fake_index is not None
    if no_index:
        drive_ticks_per_rev = args.fake_index * usb.sample_freq
    elif args.hard_sectors:
        flux = usb.read_track(revs = 0, ticks = int(usb.sample_freq / 2))
        flux.identify_hard_sectors()
        assert flux.sector_list is not None # mypy
        drive_ticks_per_rev = flux.ticks_per_rev
        args.hard_sectors = len(flux.sector_list[-1])
        hard_sector_ticks = int(drive_ticks_per_rev / args.hard_sectors)
        print(f'Drive reports {args.hard_sectors} hard sectors')
        del flux
    else:
        drive_ticks_per_rev = usb.read_track(2).ticks_per_rev

    verified_count, not_verified_count = 0, 0

    for t in args.tracks:

        cyl, head = t.cyl, t.head

        track = image.get_track(cyl, head)
        if track is None and not args.erase_empty:
            continue

        tspec = f'T{cyl}.{head}'
        if t.physical_cyl != cyl or t.physical_head != head:
            tspec += f' -> Drive {t.physical_cyl}.{t.physical_head}'

        usb.seek(t.physical_cyl, t.physical_head)

        if args.gen_tg43:
            usb.set_pin(2, cyl < 43)

        if track is None:
            print(f'{tspec}: Erasing Track')
            usb.erase_track(drive_ticks_per_rev * 1.1)
            continue

        if not isinstance(track, codec.Codec) and args.fmt_cls is not None:
            track = args.fmt_cls.decode_flux(cyl, head, track)
            if track is None:
                print("%s: WARNING: Out of range for format '%s': Track "
                      "skipped" % (tspec, args.format))
                continue
            assert isinstance(track, codec.Codec)
            error.check(track.nr_missing() == 0,
                        '%s: %u missing sectors in input image'
                        % (tspec, track.nr_missing()))
        if isinstance(track, codec.Codec):
            track = track.master_track()

        if isinstance(track, MasterTrack):
            if args.reverse:
                track.reverse()
            if args.precomp is not None:
                track.precomp = args.precomp.track_precomp(cyl)
        elif args.reverse:
            track = track.flux()
            track.reverse()
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
                print(f'{tspec}: Erasing Track')
                usb.erase_track(drive_ticks_per_rev * 1.1)
            s = f'{tspec}: Writing Track'
            if retry != 0:
                s += " (Verify Failure: Retry #%u)" % retry
            else:
                s += " (%s)" % wflux.summary_string()
            print(s)
            usb.write_track(flux_list = wflux_list,
                            cue_at_index = wflux.index_cued,
                            terminate_at_index = wflux.terminate_at_index,
                            hard_sector_ticks = hard_sector_ticks)
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
            if args.hard_sectors:
                v_ticks = 0
                v_revs = cast(int, (args.hard_sectors + 1) * 2)
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
            if args.reverse:
                v_flux.reverse()
            if args.hard_sectors:
                v_flux.identify_hard_sectors()
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
              + "\n" + util.precompspec_desc
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
    index_group = parser.add_mutually_exclusive_group(required=False)
    index_group.add_argument("--fake-index", type=util.period, metavar="SPEED",
                             help="fake index pulses at SPEED")
    index_group.add_argument("--hard-sectors", action="store_true",
                             help="write to a hard-sectored disk")
    parser.add_argument("--no-verify", action="store_true",
                        help="disable verify")
    parser.add_argument("--retries", type=util.uint, default=3, metavar="N",
                        help="number of retries on verify failure")
    parser.add_argument("--precomp", type=PrecompSpec,
                        help="write precompensation")
    parser.add_argument("--reverse", action="store_true",
                        help="reverse track data (flippy disk)")
    densel_group = parser.add_mutually_exclusive_group(required=False)
    densel_group.add_argument(
        "--densel", "--dd", type=util.level, metavar="LEVEL",
        help="drive interface density select on pin 2 (H,L)")
    densel_group.add_argument(
        "--gen-tg43", action = "store_true",
        help="generate TG43 signal for 8-inch drive on pin 2")
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
        image = open_image(args, image_class)
        if args.fmt_cls is None and isinstance(image, IMG):
            args.fmt_cls = image.fmt
        if args.fmt_cls is not None:
            def_tracks = copy.copy(args.fmt_cls.tracks)
        if def_tracks is None:
            def_tracks = util.TrackSet('c=0-81:h=0-1')
        if args.tracks is not None:
            def_tracks.update_from_trackspec(args.tracks.trackspec)
        args.tracks = def_tracks
        usb = util.usb_open(args.device)
        if args.format:
            print("Format " + args.format)
        print("Writing " + str(args.tracks))
        if args.precomp is not None:
            print(args.precomp)
        try:
            if args.densel is not None or args.gen_tg43:
                prev_pin2 = usb.get_pin(2)
            if args.densel is not None:
                usb.set_pin(2, args.densel)
            util.with_drive_selected(
                lambda: write_from_image(usb, args, image), usb, args.drive)
        finally:
            if args.densel is not None or args.gen_tg43:
                usb.set_pin(2, prev_pin2)
    except USB.CmdError as err:
        print("Command Failed: %s" % err)


if __name__ == "__main__":
    main(sys.argv)

# Local variables:
# python-indent: 4
# End:
