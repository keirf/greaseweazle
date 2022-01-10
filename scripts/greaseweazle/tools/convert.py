# greaseweazle/tools/convert.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

description = "Convert between image formats."

import sys, copy

import greaseweazle.tools.read
from greaseweazle.tools import util
from greaseweazle import error
from greaseweazle.flux import Flux
from greaseweazle.codec import formats


def open_input_image(args, image_class):
    try:
        image = image_class.from_file(args.in_file)
        args.raw_image_class = True
    except TypeError:
        image = image_class.from_file(args.in_file, args.fmt_cls)
        args.raw_image_class = False
    return image


def open_output_image(args, image_class):
    image = image_class.to_file(args.out_file, args.fmt_cls, args.no_clobber)
    for opt, val in args.out_file_opts.items():
        error.check(hasattr(image, 'opts') and hasattr(image.opts, opt),
                    "%s: Invalid file option: %s" % (args.out_file, opt))
        setattr(image.opts, opt, val)
    return image


def convert(args, in_image, out_image, decoder=None):

    summary = dict()

    for t in args.tracks:

        cyl, head = t.cyl, t.head

        track = in_image.get_track(t.physical_cyl, t.physical_head)
        if track is None:
            continue

        if args.rpm is not None:
            track.scale((60/args.rpm) / track.time_per_rev)

        if decoder is None:
            dat = track
            print("T%u.%u: %s" % (cyl, head, track.summary_string()))
        else:
            dat = decoder(cyl, head, track)
            print("T%u.%u: %s from %s" % (cyl, head, dat.summary_string(),
                                          track.summary_string()))
        summary[cyl,head] = dat

    for t in args.out_tracks:
        cyl, head = t.cyl, t.head
        if (cyl, head) not in summary:
            continue
        dat = summary[cyl,head]
        out_image.emit_track(t.physical_cyl, t.physical_head, dat)

    if decoder is not None:
        greaseweazle.tools.read.print_summary(args, summary)


def main(argv):

    epilog = "FORMAT options:\n" + formats.print_formats()
    parser = util.ArgumentParser(usage='%(prog)s [options] in_file out_file',
                                 epilog=epilog)
    parser.add_argument("--format", help="disk format")
    parser.add_argument("--tracks", type=util.TrackSet,
                        help="which tracks to read & convert from input",
                        metavar="TSPEC")
    parser.add_argument("--out-tracks", type=util.TrackSet,
                        help="which tracks to output (default: --tracks)",
                        metavar="TSPEC")
    parser.add_argument("--rpm", type=int, help="convert drive speed to RPM",
                        metavar="N")
    parser.add_argument("-n", "--no-clobber", action="store_true",
                        help="do not overwrite an existing file")
    parser.add_argument("in_file", help="input filename")
    parser.add_argument("out_file", help="output filename")
    parser.description = description
    parser.prog += ' ' + argv[1]
    args = parser.parse_args(argv[2:])

    args.out_file, args.out_file_opts = util.split_opts(args.out_file)

    in_image_class = util.get_image_class(args.in_file)
    if not args.format and hasattr(in_image_class, 'default_format'):
        args.format = in_image_class.default_format

    out_image_class = util.get_image_class(args.out_file)
    if not args.format and hasattr(out_image_class, 'default_format'):
        args.format = out_image_class.default_format

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
        def_tracks = copy.copy(args.fmt_cls.default_tracks)
    if def_tracks is None:
        def_tracks = util.TrackSet('c=0-81:h=0-1')
    out_def_tracks = copy.copy(def_tracks)
    if args.tracks is not None:
        def_tracks.update_from_trackspec(args.tracks.trackspec)
        out_def_tracks.cyls = copy.copy(def_tracks.cyls)
        out_def_tracks.heads = copy.copy(def_tracks.heads)
    args.tracks = def_tracks
    if args.out_tracks is not None:
        out_def_tracks.update_from_trackspec(args.out_tracks.trackspec)
    args.out_tracks = out_def_tracks

    print("Converting %s -> %s" % (args.tracks, args.out_tracks))
    if args.format:
        print("Format " + args.format)

    in_image = open_input_image(args, in_image_class)
    with open_output_image(args, out_image_class) as out_image:
        convert(args, in_image, out_image, decoder=decoder)


# Local variables:
# python-indent: 4
# End:
