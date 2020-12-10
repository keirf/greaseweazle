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


def open_image(args, image_class):
    image = image_class.to_file(args.file)
    if args.rate is not None:
        image.bitrate = args.rate
    for opt, val in args.file_opts.items():
        error.check(hasattr(image, 'opts') and hasattr(image.opts, opt),
                    "%s: Invalid file option: %s" % (args.file, opt))
        setattr(image.opts, opt, val)
    return image


def normalise_rpm(flux, rpm):
    """Adjust all revolutions in Flux object to have specified rotation speed.
    """

    index_list, freq = flux.index_list, flux.sample_freq
    
    norm_to_index = 60/rpm * flux.sample_freq
    norm_flux = []

    to_index, index_list = index_list[0], index_list[1:]
    factor = norm_to_index / to_index
    
    for x in flux.list:
        to_index -= x
        if to_index >= 0:
            norm_flux.append(x*factor)
            continue
        if not index_list:
            break
        n_to_index, index_list = index_list[0], index_list[1:]
        n_factor = norm_to_index / n_to_index
        norm_flux.append((x+to_index)*factor - to_index*n_factor)
        to_index, factor = n_to_index, n_factor

    return Flux([norm_to_index]*len(flux.index_list), norm_flux, freq)


def read_and_normalise(usb, args, revs):
    flux = usb.read_track(revs)
    if args.rpm is not None:
        flux = normalise_rpm(flux, args.rpm)
    return flux


def read_with_retry(usb, args, cyl, head, decoder):
    flux = read_and_normalise(usb, args, args.revs)
    if decoder is None:
        return flux
    dat = decoder(cyl, head, flux)
    if dat.nr_missing() != 0:
        for retry in range(3):
            print("T%u.%u: %s - %d sectors missing - Retrying (%d)"
                  % (cyl, head, dat.summary_string(),
                     dat.nr_missing(), retry+1))
            flux = read_and_normalise(usb, args, max(args.revs, 3))
            dat.decode_raw(flux)
            if dat.nr_missing() == 0:
                break
    return dat


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

    summary = dict()

    for t in args.tracks:
        cyl, head = t.cyl, t.head
        usb.seek(t.physical_cyl, head)
        dat = read_with_retry(usb, args, cyl, head, decoder)
        print("T%u.%u: %s" % (cyl, head, dat.summary_string()))
        summary[cyl,head] = dat
        image.emit_track(cyl, head, dat)

    if decoder is not None:
        print_summary(args, summary)


def main(argv):

    parser = util.ArgumentParser(usage='%(prog)s [options] file')
    parser.add_argument("--device", help="greaseweazle device name")
    parser.add_argument("--drive", type=util.drive_letter, default='A',
                        help="drive to read (A,B,0,1,2)")
    parser.add_argument("--format", help="disk format")
    parser.add_argument("--revs", type=int,
                        help="number of revolutions to read per track")
    parser.add_argument("--tracks", type=util.TrackSet,
                        help="which tracks to read")
    parser.add_argument("--rate", type=int, help="data rate (kbit/s)")
    parser.add_argument("--rpm", type=int, help="convert drive speed to RPM")
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
        decoder, def_tracks = None, None
        if args.format:
            try:
                mod = importlib.import_module('greaseweazle.codec.'
                                              + args.format)
                decoder = mod.decode_track
            except (ModuleNotFoundError, AttributeError) as ex:
                raise error.Fatal("Unknown format '%s'" % args.format) from ex
            def_tracks = util.TrackSet(mod.default_trackset)
            if args.revs is None: args.revs = mod.default_revs
        if def_tracks is None:
            def_tracks = util.TrackSet('c=0-81:h=0-1')
        if args.revs is None: args.revs = 3
        if args.tracks is not None:
            def_tracks.update_from_trackspec(args.tracks.trackspec)
        args.tracks = def_tracks
        
        print("Reading %s revs=%d" % (args.tracks, args.revs))
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
