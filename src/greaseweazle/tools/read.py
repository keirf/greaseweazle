# greaseweazle/tools/read.py
#
# Greaseweazle control script: Read Disk to Image.
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

description = "Read a disk to the specified image file."

from typing import cast, Dict, Tuple, List, Type, Optional

import sys, copy

from greaseweazle.tools import util
from greaseweazle import error
from greaseweazle import usb as USB
from greaseweazle.flux import Flux, HasFlux
from greaseweazle.codec import codec
from greaseweazle.image import image

from greaseweazle import track
plls = track.plls

def open_image(args, image_class: Type[image.Image]) -> image.Image:
    image = image_class.to_file(
        args.file, None if args.raw else args.fmt_cls, args.no_clobber,
        args.file_opts)
    image.write_on_ctrl_c = True
    return image


def read_and_normalise(usb: USB.Unit, args, revs: int, ticks=0) -> Flux:
    if args.fake_index is not None:
        drive_tpr = int(args.drive_ticks_per_rev)
        pre_index = int(usb.sample_freq * 0.5e-3)
        if ticks == 0:
            ticks = revs*drive_tpr + 2*pre_index
        flux = usb.read_track(revs=0, ticks=ticks)
        index_list = [pre_index] + [drive_tpr] * ((ticks-pre_index)//drive_tpr)
        flux.index_list = cast(List[float], index_list) # mypy
    else:
        flux = usb.read_track(revs=revs, ticks=ticks)
    flux._ticks_per_rev = args.drive_ticks_per_rev
    if args.reverse:
        flux.reverse()
    if args.hard_sectors and not args.raw:
        flux.identify_hard_sectors()
    if args.adjust_speed is not None:
        flux.scale(args.adjust_speed / flux.time_per_rev)
    return flux


def read_with_retry(usb: USB.Unit, args, t) -> Tuple[Flux, Optional[HasFlux]]:

    cyl, head = t.cyl, t.head

    tspec = f'T{cyl}.{head}'
    if t.physical_cyl != cyl or t.physical_head != head:
        tspec += f' <- Drive {t.physical_cyl}.{t.physical_head}'

    usb.seek(t.physical_cyl, t.physical_head)

    if args.gen_tg43:
        usb.set_pin(2, cyl < 60)

    flux = read_and_normalise(usb, args, args.revs, args.ticks)
    if args.fmt_cls is None:
        print(f'{tspec}: {flux.summary_string()}')
        return flux, flux

    dat = args.fmt_cls.decode_flux(cyl, head, flux)
    if dat is None:
        print("%s: WARNING: Out of range for format '%s': No format "
              "conversion applied: %s" % (tspec, args.format,
                flux.summary_string()))
        return flux, None
    for pll in plls[1:]:
        if dat.nr_missing() == 0:
            break
        dat.decode_flux(flux, pll)

    seek_retry, retry = 0, 0
    while True:
        s = "%s: %s from %s" % (tspec, dat.summary_string(),
                                    flux.summary_string())
        if retry != 0:
            s += " (Retry #%u.%u)" % (seek_retry, retry)
        print(s)
        if dat.nr_missing() == 0:
            break
        if args.retries == 0 or (retry % args.retries) == 0:
            if args.retries == 0 or seek_retry > args.seek_retries:
                print("%s: Giving up: %d sectors missing"
                      % (tspec, dat.nr_missing()))
                break
            if retry != 0:
                usb.seek(0, 0)
                usb.seek(t.physical_cyl, t.physical_head)
                if args.gen_tg43:
                    usb.set_pin(2, cyl < 60)
            seek_retry += 1
            retry = 0
        retry += 1
        _flux = read_and_normalise(usb, args, max(args.revs, 3))
        for pll in plls:
            if dat.nr_missing() == 0:
                break
            dat.decode_flux(_flux, pll)
        if args.raw:
            flux.append(_flux)
        else:
            flux = _flux

    return flux, dat


def print_summary(args, summary: Dict[Tuple[int,int],codec.Codec]) -> None:
    if not summary:
        return
    nsec = max((summary[x].nsec for x in summary), default = None)
    if nsec is None or nsec == 0:
        return
    s = 'Cyl-> '
    p = -1
    for c in args.tracks.cyls:
        s += ' ' if c//10==p else str(c//10)
        p = c//10
    print(s)
    s = 'H. S: '
    for c in args.tracks.cyls:
        s += str(c%10)
    print(s)
    tot_sec = good_sec = 0
    for head in args.tracks.heads:
        nsec = max((summary[x].nsec for x in summary if x[1] == head),
                   default = None)
        if nsec is None:
            continue
        for sec in range(nsec):
            print("%d.%2d: " % (head, sec), end="")
            for cyl in args.tracks.cyls:
                t = summary.get((cyl,head), None)
                if t is None or sec >= t.nsec:
                    print(" ", end="")
                else:
                    tot_sec += 1
                    if t.has_sec(sec): good_sec += 1
                    print("." if t.has_sec(sec) else "X", end="")
            print()
    if tot_sec != 0:
        print("Found %d sectors of %d (%d%%)" %
              (good_sec, tot_sec, good_sec*100/tot_sec))


def read_to_image(usb: USB.Unit, args, image: image.Image) -> None:
    """Reads a floppy disk and dumps it into a new image file.
    """

    args.ticks, args.drive_ticks_per_rev = 0, None

    if args.fake_index is not None:
        args.drive_ticks_per_rev = args.fake_index * usb.sample_freq
    elif args.hard_sectors:
        flux = usb.read_track(revs = 0, ticks = int(usb.sample_freq / 2))
        flux.identify_hard_sectors()
        assert flux.sector_list is not None # mypy
        args.drive_ticks_per_rev = flux.ticks_per_rev
        args.hard_sectors = len(flux.sector_list[-1])
        print(f'Drive reports {args.hard_sectors} hard sectors')
        del flux

    if isinstance(args.revs, float):
        if args.raw:
            # If dumping raw flux we want full index-to-index revolutions.
            args.revs = 2
        else:
            # Measure drive RPM.
            # We will adjust the flux intervals per track to allow for this.
            if args.drive_ticks_per_rev is None:
                args.drive_ticks_per_rev = usb.read_track(2).ticks_per_rev
            args.ticks = int(args.drive_ticks_per_rev * args.revs)
            args.revs = 2

    if args.hard_sectors:
        # Hard-sectored disks have "hard_sectors + 1" holes.
        # We read an extra revolution's worth to be sure we get the requested
        # number of full index-to-index revolutions.
        args.revs = (args.hard_sectors + 1) * (args.revs + 1)
        args.ticks = 0

    summary: Dict[Tuple[int,int],codec.Codec] = dict()

    for t in args.tracks:
        cyl, head = t.cyl, t.head
        flux, dat = read_with_retry(usb, args, t)
        if args.fmt_cls is not None and dat is not None:
            assert isinstance(dat, codec.Codec)
            summary[cyl,head] = dat
        if args.raw:
            image.emit_track(cyl, head, flux)
        elif dat is not None:
            image.emit_track(cyl, head, dat)

    if args.fmt_cls is not None:
        print_summary(args, summary)


def main(argv) -> None:

    epilog = (util.drive_desc + "\n"
              + util.speed_desc + "\n" + util.tspec_desc
              + "\n" + util.pllspec_desc
              + "\nFORMAT options:\n" + codec.print_formats()
              + "\n\nSupported file suffixes:\n"
              + util.columnify(util.image_types))
    parser = util.ArgumentParser(usage='%(prog)s [options] file',
                                 epilog=epilog)
    parser.add_argument("--device", help="device name (COM/serial port)")
    parser.add_argument("--drive", type=util.Drive(), default='A',
                        help="drive to read")
    parser.add_argument("--diskdefs", help="disk definitions file")
    parser.add_argument("--format", help="disk format (output is converted unless --raw)")
    parser.add_argument("--revs", type=util.min_int(1), metavar="N",
                        help="number of revolutions to read per track")
    parser.add_argument("--tracks", type=util.TrackSet, metavar="TSPEC",
                        help="which tracks to read")
    parser.add_argument("--raw", action="store_true",
                        help="output raw stream (--format verifies only)")
    index_group = parser.add_mutually_exclusive_group(required=False)
    index_group.add_argument("--fake-index", type=util.period, metavar="SPEED",
                             help="fake index pulses at SPEED")
    index_group.add_argument("--hard-sectors", action="store_true",
                             help="read from a hard-sectored disk")
    parser.add_argument("--adjust-speed", type=util.period, metavar="SPEED",
                        help="scale track data to effective drive SPEED")
    parser.add_argument("--retries", type=util.uint, default=3, metavar="N",
                        help="number of retries per seek-retry")
    parser.add_argument("--seek-retries", type=util.uint, default=0,
                        metavar="N",
                        help="number of seek retries")
    parser.add_argument("-n", "--no-clobber", action="store_true",
                        help="do not overwrite an existing file")
    parser.add_argument("--pll", type=track.PLL, metavar="PLLSPEC",
                        help="manual PLL parameter override")
    densel_group = parser.add_mutually_exclusive_group(required=False)
    densel_group.add_argument("--densel", "--dd", type=util.level, metavar="LEVEL",
                        help="drive interface density select on pin 2 (H,L)")
    densel_group.add_argument("--gen-tg43", action="store_true",
                        help="generate TG43 signal for 8-inch drive on pin 2 from track 60. Enable postcompensation filter")
    parser.add_argument("--reverse", action="store_true",
                        help="reverse track data (flippy disk)")
    parser.add_argument("file", help="output filename")
    parser.description = description
    parser.prog += ' ' + argv[1]
    args = parser.parse_args(argv[2:])

    args.file, args.file_opts = util.split_opts(args.file)

    if args.pll is not None:
        plls.insert(0, args.pll)

    try:
        usb = util.usb_open(args.device)
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
            if args.revs is None: args.revs = args.fmt_cls.default_revs
        if def_tracks is None:
            def_tracks = util.TrackSet('c=0-81:h=0-1')
        if args.revs is None: args.revs = 3
        if args.tracks is not None:
            def_tracks.update_from_trackspec(args.tracks.trackspec)
        args.tracks = def_tracks

        print(("Reading %s revs=" % args.tracks) + str(args.revs))
        if args.format:
            print("Format " + args.format)
        try:
            if args.densel is not None or args.gen_tg43:
                prev_pin2 = usb.get_pin(2)
            if args.densel is not None:
                usb.set_pin(2, args.densel)
            with open_image(args, image_class) as image:
                util.with_drive_selected(
                    lambda: read_to_image(usb, args, image), usb, args.drive)
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
