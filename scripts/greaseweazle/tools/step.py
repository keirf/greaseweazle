# greaseweazle/tools/step.py
#
# Greaseweazle control script: Exercise head stepper motor.
#
# Written & released by Alistair Buxton <a.j.buxton@gmail.com>
# Based on erase.py by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import sys

from greaseweazle.tools import util
from greaseweazle import usb as USB

def step(usb, args):
    while args.repeat != 0:
        usb.seek(args.ecyl, 0)
        usb.seek(args.scyl, 0)
        args.repeat -= 1

def main(argv):

    parser = util.ArgumentParser()
    parser.add_argument("--drive", type=util.drive_letter, default='A',
                        help="drive to write (A,B,0,1,2)")
    parser.add_argument("--scyl", type=int, default=0,
                        help="first cylinder to write")
    parser.add_argument("--ecyl", type=int, default=81,
                        help="last cylinder to write")
    parser.add_argument("--repeat", type=int, default=0,
                        help="times to repeat (0 = forever)")
    parser.add_argument("device", nargs="?", default="auto",
                        help="serial device")
    parser.prog += ' ' + argv[1]
    args = parser.parse_args(argv[2:])
    args.repeat = args.repeat if args.repeat else -1

    try:
        usb = util.usb_open(args.device)
        util.with_drive_selected(step, usb, args)
    except USB.CmdError as error:
        print("Command Failed: %s" % error)


if __name__ == "__main__":
    main(sys.argv)

# Local variables:
# python-indent: 4
# End:
