# greaseweazle/tools/read.py
#
# Greaseweazle control script: Read Disk to Image.
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

description = "Read a disk to the specified image file."

import sys
import importlib

from greaseweazle.tools import util
from greaseweazle import error
from greaseweazle import usb as USB
from greaseweazle.flux import Flux
from greaseweazle.codec import formats


def open_image(args, image_class):
    image = image_class.to_file(
        args.file, None if args.raw else args.fmt_cls, args.no_clobber)
    for opt, val in args.file_opts.items():
        error.check(hasattr(image, 'opts') and hasattr(image.opts, opt),
                    "%s: Invalid file option: %s" % (args.file, opt))
        setattr(image.opts, opt, val)
    return image


def read_and_normalise(usb, args, revs, ticks=0):
    flux = usb.read_track(revs=revs, ticks=ticks)
    if args.rpm is not None:
        flux.scale((60/args.rpm) / flux.time_per_rev)
    return flux


def read_with_retry(usb, args, cyl, head, decoder):

    flux = read_and_normalise(usb, args, args.revs, args.ticks)
    if decoder is None:
        print("T%u.%u: %s" % (cyl, head, flux.summary_string()))
        return flux, flux

    dat = decoder(cyl, head, flux)

    retry = 0
    while True:
        print("T%u.%u: %s from %s" % (cyl, head, dat.summary_string(),
                                      flux.summary_string()))
        if dat.nr_missing() == 0:
            break
        if retry == args.retries:
            print("T%u.%u: Giving up: %d sectors missing"
                  % (cyl, head, dat.nr_missing()))
            break
        retry += 1
        print("T%u.%u: Retry #%d" % (cyl, head, retry))
        _flux = read_and_normalise(usb, args, max(args.revs, 3))
        dat.decode_raw(_flux)
        flux.append(_flux)

    return flux, dat


def print_summary(args, summary):
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
        nsec = max(summary[x].nsec for x in summary if x[1] == head)
        for sec in range(nsec):
            print("%d.%2d: " % (head, sec), end="")
            for cyl in args.tracks.cyls:
                s = summary[cyl,head]
                if sec > s.nsec:
                    print(" ", end="")
                else:
                    tot_sec += 1
                    if s.has_sec(sec): good_sec += 1
                    print("." if s.has_sec(sec) else "X", end="")
            print()
    if tot_sec != 0:
        print("Found %d sectors of %d (%d%%)" %
              (good_sec, tot_sec, good_sec*100/tot_sec))


def read_to_image(usb, args, image, decoder=None):
    """Reads a floppy disk and dumps it into a new image file.
    """

    args.ticks = 0
    if isinstance(args.revs, float):
        # Measure drive RPM.
        # We will adjust the flux intervals per track to allow for this.
        args.ticks = int(usb.read_track(2).ticks_per_rev * args.revs)
        args.revs = 2

    summary = dict()

    for t in args.tracks:
        cyl, head = t.cyl, t.head
        usb.seek(t.physical_cyl, t.physical_head)
        flux, dat = read_with_retry(usb, args, cyl, head, decoder)
        if decoder is not None:
            summary[cyl,head] = dat
        image.emit_track(cyl, head, flux if args.raw else dat)

    if decoder is not None:
        print_summary(args, summary)


def main(argv):

    epilog = "FORMAT options:\n" + formats.print_formats()
    parser = util.ArgumentParser(usage='%(prog)s [options] file',
                                 epilog=epilog)
    parser.add_argument("--device", help="device name (COM/serial port)")
    parser.add_argument("--drive", type=util.drive_letter, default='A',
                        help="drive to read (A,B,0,1,2)")
    parser.add_argument("--format", help="disk format (output is converted unless --raw)")
    parser.add_argument("--revs", type=int,
                        help="number of revolutions to read per track")
    parser.add_argument("--tracks", type=util.TrackSet,
                        help="which tracks to read")
    parser.add_argument("--raw", action="store_true",
                        help="output raw stream (--format verifies only)")
    parser.add_argument("--rpm", type=int, help="convert drive speed to RPM")
    parser.add_argument("--retries", type=int, default=3,
                        help="number of retries on decode failure")
    parser.add_argument("-n", "--no-clobber", action="store_true",
                        help="do not overwrite an existing file")
    parser.add_argument("file", help="output filename")
    parser.description = description
    parser.prog += ' ' + argv[1]
    args = parser.parse_args(argv[2:])

    args.file, args.file_opts = util.split_opts(args.file)

    try:
        usb = util.usb_open(args.device)
        image_class = util.get_image_class(args.file)
        if not args.format and hasattr(image_class, 'default_format'):
            args.format = image_class.default_format
        decoder, def_tracks, args.fmt_cls = None, None, None
        if args.format:
            try:
                args.fmt_cls = formats.formats[args.format]()
            except KeyError as ex:
                raise error.Fatal("""\
Unknown format '%s'
Known formats:\n%s"""
                                  % (args.format, formats.print_formats()))
            decoder = args.fmt_cls.decode_track
            def_tracks = args.fmt_cls.default_tracks
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
        with open_image(args, image_class) as image:
            util.with_drive_selected(read_to_image, usb, args, image,
                                     decoder=decoder)
    except USB.CmdError as err:
        print("Command Failed: %s" % err)


if __name__ == "__main__":
    main(sys.argv)

# Local variables:
# python-indent: 4
# End:
