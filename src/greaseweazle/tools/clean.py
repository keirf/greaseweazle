# greaseweazle/tools/clean.py
#
# Greaseweazle control script: Scrub drive heads with a cleaning disk.
#
# Uses a zig-zag pattern, after Dave Dunfield's ImageDisk and
# Phil Pemberton's Magpie/DiscFerret.
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

description = "Clean a drive in a zig-zag pattern using a cleaning disk."

import sys, time

from greaseweazle.tools import util
from greaseweazle import usb as USB

def seek(cyl: int, usb: USB.Unit, args) -> None:
    c = min(cyl, args.cyls - 1)
    print("%d " % c, end='', flush=True)
    usb.seek(c, 0)

def clean(usb: USB.Unit, args) -> None:
    step = max(args.cyls // 8, 2)
    for p in range(args.passes):
        print('Pass %d: ' % p, end='', flush=True)
        for cyl in range(0, args.cyls, step):
            seek(cyl + step - 1, usb, args)
            time.sleep(args.linger / 1000)
            seek(cyl, usb, args)
            time.sleep(args.linger / 1000)
        print()

def main(argv) -> None:

    epilog = (util.drive_desc)
    parser = util.ArgumentParser(usage='%(prog)s [options]',
                                 epilog=epilog)
    parser.add_argument("--device", help="device name (COM/serial port)")
    parser.add_argument("--drive", type=util.Drive(), default='A',
                        help="drive to read")
    parser.add_argument("--cyls", type=util.uint, default=80, metavar="N",
                        help="number of drive cylinders")
    parser.add_argument("--passes", type=util.uint, default=3, metavar="N",
                        help="number of passes across the cleaning disk")
    parser.add_argument("--linger", type=util.uint, default=100, metavar="N",
                        help="linger time per step, milliseconds")
    parser.description = description
    parser.prog += ' ' + argv[1]
    args = parser.parse_args(argv[2:])

    try:
        usb = util.usb_open(args.device)
        util.with_drive_selected(lambda: clean(usb, args), usb, args.drive)
    except USB.CmdError as error:
        print("Command Failed: %s" % error)


if __name__ == "__main__":
    main(sys.argv)

# Local variables:
# python-indent: 4
# End:
