# greaseweazle/tools/write.py
#
# Greaseweazle control script: Write Image to Disk.
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import sys, argparse

from greaseweazle.tools import util
from greaseweazle import usb as USB

# write_from_image:
# Writes the specified image file to floppy disk.
def write_from_image(usb, args):

    if args.adjust_speed:
        # @drive_ticks is the time in Gresaeweazle ticks between index pulses.
        # We will adjust the flux intervals per track to allow for this.
        flux = usb.read_track(2)
        drive_ticks = (flux.index_list[0] + flux.index_list[1]) / 2
        del flux

    # Read and parse the image file.
    image_class = util.get_image_class(args.file)
    if not image_class:
        return
    with open(args.file, "rb") as f:
        image = image_class.from_file(f.read())

    for cyl in range(args.scyl, args.ecyl+1):
        for side in range(0, args.nr_sides):

            flux = image.get_track(cyl, side, writeout=True)
            if not flux:
                continue

            print("\rWriting Track %u.%u..." % (cyl, side), end="")
            usb.seek(cyl, side)

            if args.adjust_speed:
                # @factor adjusts flux times for speed variations between the
                # read-in and write-out drives.
                factor = drive_ticks / flux.index_list[0]
            else:
                # Simple ratio between the GW and image sample frequencies.
                factor = usb.sample_freq / flux.sample_freq

            # Convert the flux samples to Greaseweazle sample frequency.
            rem = 0.0
            flux_list = []
            for x in flux.list:
                y = x * factor + rem
                val = int(round(y))
                rem = y - val
                flux_list.append(val)

            # Encode the flux times for Greaseweazle, and write them out.
            usb.write_track(flux_list)

    print()


def main(argv):

    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--scyl", type=int, default=0,
                        help="first cylinder to write")
    parser.add_argument("--ecyl", type=int, default=81,
                        help="last cylinder to write")
    parser.add_argument("--single-sided", action="store_true",
                        help="single-sided write")
    parser.add_argument("--adjust-speed", action="store_true",
                        help="adjust write-flux times for drive speed")
    parser.add_argument("file", help="input filename")
    parser.add_argument("device", help="serial device")
    parser.prog += ' ' + argv[1]
    args = parser.parse_args(argv[2:])
    args.nr_sides = 1 if args.single_sided else 2

    try:
        usb = util.usb_open(args.device)
        util.with_drive_selected(write_from_image, usb, args)
    except USB.CmdError as error:
        print("Command Failed: %s" % error)


if __name__ == "__main__":
    main(sys.argv)

# Local variables:
# python-indent: 4
# End:
