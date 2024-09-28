# greaseweazle/tools/convert.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

description = "Convert between image formats."

from typing import Dict, Tuple, Optional, Type

import sys, copy

import greaseweazle.tools.read
from greaseweazle.tools import util
from greaseweazle import error
from greaseweazle.flux import Flux, HasFlux
from greaseweazle.codec import codec
from greaseweazle.track import MasterTrack
from greaseweazle.image.image import Image
from greaseweazle.image.img import IMG

from greaseweazle import track
plls = track.plls

def open_input_image(args, image_class: Type[Image]) -> Image:
    return image_class.from_file(args.in_file, args.fmt_cls, args.in_file_opts)


def open_output_image(args, image_class: Type[Image]) -> Image:
    return image_class.to_file(args.out_file, args.fmt_cls, args.no_clobber,
                               args.out_file_opts)

class TrackIdentity:
    def __init__(self, ts: util.TrackSet, cyl: int, head: int) -> None:
        self.cyl, self.head = cyl, head
        self.physical_cyl, self.physical_head = ts.ch_to_pch(cyl, head)


def process_input_track(
        args,
        t: TrackIdentity,
        in_image: Image
) -> Optional[HasFlux]:

    cyl, head = t.cyl, t.head
    dat: Optional[HasFlux]

    tspec = f'T{cyl}.{head}'
    if t.physical_cyl != cyl or t.physical_head != head:
        tspec += f' <- Image {t.physical_cyl}.{t.physical_head}'

    track = in_image.get_track(t.physical_cyl, t.physical_head)
    if track is None:
        return None

    if args.reverse:
        track = track.flux()
        track.reverse()

    if args.hard_sectors:
        track = track.flux()
        track.identify_hard_sectors()
        assert track.sector_list is not None # mypy
        print('%s: Converted to %u hard sectors'
              % (tspec, len(track.sector_list[-1])))

    if args.adjust_speed is not None:
        if isinstance(track, codec.Codec):
            track = track.master_track()
        if not isinstance(track, MasterTrack):
            track = track.flux()
        track.scale(args.adjust_speed / track.time_per_rev)

    if args.fmt_cls is None or isinstance(track, codec.Codec):
        dat = track
        print("%s: %s" % (tspec, track.summary_string()))
    else:
        dat = args.fmt_cls.decode_flux(cyl, head, track)
        if dat is None:
            print("%s: WARNING: Out of range for format '%s': Track "
                  "skipped" % (tspec, args.format))
            return None
        assert isinstance(dat, codec.Codec)
        for pll in plls[1:]:
            if dat.nr_missing() == 0:
                break
            dat.decode_flux(track, pll)
        print("%s: %s from %s" % (tspec, dat.summary_string(),
                                  track.summary_string()))

    return dat


def convert(args, in_image: Image, out_image: Image) -> None:

    summary: Dict[Tuple[int,int],codec.Codec] = dict()
    dat: Optional[HasFlux]

    for t in args.out_tracks:
        cyl, head = t.cyl, t.head
        if (cyl, head) in summary:
            dat = summary[cyl, head]
        elif (cyl, head) in args.tracks:
            dat = process_input_track(
                args, TrackIdentity(args.tracks, cyl, head), in_image)
            if dat is None:
                continue
            if args.fmt_cls is not None:
                assert isinstance(dat, codec.Codec)
                summary[cyl,head] = dat
        else:
            continue
        out_image.emit_track(t.physical_cyl, t.physical_head, dat)

    greaseweazle.tools.read.print_summary(args, summary)


def main(argv) -> None:

    epilog = (util.speed_desc + "\n" + util.tspec_desc
              + "\n" + util.pllspec_desc
              + "\nFORMAT options:\n" + codec.print_formats()
              + "\n\nSupported file suffixes:\n"
              + util.columnify(util.image_types))
    parser = util.ArgumentParser(usage='%(prog)s [options] in_file out_file',
                                 epilog=epilog)
    parser.add_argument("--diskdefs", help="disk definitions file")
    parser.add_argument("--format", help="disk format")
    parser.add_argument("--tracks", type=util.TrackSet,
                        help="which tracks to read & convert from input",
                        metavar="TSPEC")
    parser.add_argument("--out-tracks", type=util.TrackSet,
                        help="which tracks to output (default: --tracks)",
                        metavar="TSPEC")
    parser.add_argument("--adjust-speed", type=util.period, metavar="SPEED",
                        help="scale track data to effective drive SPEED")
    parser.add_argument("-n", "--no-clobber", action="store_true",
                        help="do not overwrite an existing file")
    parser.add_argument("--pll", type=track.PLL, metavar="PLLSPEC",
                        help="manual PLL parameter override")
    parser.add_argument("--hard-sectors", action="store_true",
                        help="convert index positions to hard sectors")
    parser.add_argument("--reverse", action="store_true",
                        help="reverse track data (flippy disk)")
    parser.add_argument("in_file", help="input filename")
    parser.add_argument("out_file", help="output filename")
    parser.description = description
    parser.prog += ' ' + argv[1]
    args = parser.parse_args(argv[2:])

    args.in_file, args.in_file_opts = util.split_opts(args.in_file)
    args.out_file, args.out_file_opts = util.split_opts(args.out_file)

    if args.pll is not None:
        plls.insert(0, args.pll)

    in_image_class = util.get_image_class(args.in_file)
    if not args.format:
        args.format = in_image_class.default_format

    out_image_class = util.get_image_class(args.out_file)
    if not args.format:
        args.format = out_image_class.default_format

    def_tracks, args.fmt_cls = None, None
    if args.format:
        args.fmt_cls = codec.get_diskdef(args.format, args.diskdefs)
        if args.fmt_cls is None:
            raise error.Fatal("""\
Unknown format '%s'
Known formats:\n%s"""
                              % (args.format, codec.print_formats(
                                  args.diskdefs)))
    in_image = open_input_image(args, in_image_class)
    if args.fmt_cls is None and isinstance(in_image, IMG):
        args.fmt_cls = in_image.fmt
    if args.fmt_cls is not None:
        def_tracks = copy.copy(args.fmt_cls.tracks)
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

    if args.format:
        print("Format " + args.format)
    print("Converting %s -> %s" % (args.tracks, args.out_tracks))

    with open_output_image(args, out_image_class) as out_image:
        convert(args, in_image, out_image)


# Local variables:
# python-indent: 4
# End:
