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

from greaseweazle.tools import util
from greaseweazle import error
from greaseweazle import usb as USB
from greaseweazle.flux import Flux


def open_image(args):
    image_class = util.get_image_class(args.file)
    error.check(hasattr(image_class, 'to_file'),
                "%s: Cannot create %s image files"
                % (args.file, image_class.__name__))
    image = image_class.to_file(args.scyl, args.nr_sides)
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


def read_to_image(usb, args, image):
    """Reads a floppy disk and dumps it into a new image file.
    """

    for cyl in range(args.scyl, args.ecyl+1):
        for side in range(0, args.nr_sides):
            print("\rReading Track %u.%u..." % (cyl, side), end="")
            usb.seek((cyl, cyl*2)[args.double_step], side)
            flux = usb.read_track(args.revs)
            if args.rpm is not None:
                flux = normalise_rpm(flux, args.rpm)
            image.append_track(flux)

    print()

    # Write the image file.
    with open(args.file, "wb") as f:
        f.write(image.get_image())


def main(argv):

    parser = util.ArgumentParser(usage='%(prog)s [options] file')
    parser.add_argument("--device", help="greaseweazle device name")
    parser.add_argument("--drive", type=util.drive_letter, default='A',
                        help="drive to read (A,B,0,1,2)")
    parser.add_argument("--revs", type=int, default=3,
                        help="number of revolutions to read per track")
    parser.add_argument("--scyl", type=int, default=0,
                        help="first cylinder to read")
    parser.add_argument("--ecyl", type=int, default=81,
                        help="last cylinder to read")
    parser.add_argument("--single-sided", action="store_true",
                        help="single-sided read")
    parser.add_argument("--double-step", action="store_true",
                        help="double-step drive heads")
    parser.add_argument("--rate", type=int, help="data rate (kbit/s)")
    parser.add_argument("--rpm", type=int, help="convert drive speed to RPM")
    parser.add_argument("file", help="output filename")
    parser.description = description
    parser.prog += ' ' + argv[1]
    args = parser.parse_args(argv[2:])
    args.nr_sides = 1 if args.single_sided else 2

    args.file, args.file_opts = util.split_opts(args.file)

    try:
        usb = util.usb_open(args.device)
        image = open_image(args)
        util.with_drive_selected(read_to_image, usb, args, image)
    except USB.CmdError as error:
        print("Command Failed: %s" % error)


if __name__ == "__main__":
    main(sys.argv)

# Local variables:
# python-indent: 4
# End:
