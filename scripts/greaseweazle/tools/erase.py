# greaseweazle/tools/erase.py
#
# Greaseweazle control script: Erase a Disk.
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

description = "Erase a disk."

import sys

from greaseweazle.tools import util
from greaseweazle import usb as USB

def erase(usb, args):

    # @drive_ticks is the time in Greaseweazle ticks between index pulses.
    # We will adjust the flux intervals per track to allow for this.
    flux = usb.read_track(2)
    drive_ticks = (flux.index_list[0] + flux.index_list[1]) / 2
    del flux

    for cyl in range(args.scyl, args.ecyl+1):
        for side in range(0, args.nr_sides):
            print("\rErasing Track %u.%u..." % (cyl, side), end="")
            usb.seek(cyl, side)
            usb.erase_track(drive_ticks * 1.1)

    print()


def main(argv):

    parser = util.ArgumentParser()
    parser.add_argument("--drive", type=util.drive_letter, default='A',
                        help="drive to write (A,B,0,1,2)")
    parser.add_argument("--scyl", type=int, default=0,
                        help="first cylinder to write")
    parser.add_argument("--ecyl", type=int, default=81,
                        help="last cylinder to write")
    parser.add_argument("--single-sided", action="store_true",
                        help="single-sided write")
    parser.add_argument("device", nargs="?", help="serial device")
    parser.description = description
    parser.prog += ' ' + argv[1]
    args = parser.parse_args(argv[2:])
    args.nr_sides = 1 if args.single_sided else 2

    try:
        usb = util.usb_open(args.device)
        util.with_drive_selected(erase, usb, args)
    except USB.CmdError as error:
        print("Command Failed: %s" % error)


if __name__ == "__main__":
    main(sys.argv)

# Local variables:
# python-indent: 4
# End:
