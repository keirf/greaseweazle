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
from greaseweazle.usb import CmdError, Ack


def seek_with_catch_notrk0(usb, cyl, wait):
    if wait:
        input('Press enter to seek to track {:d}.'.format(cyl))
    try:
        usb.seek(cyl, 0)
    except CmdError as e:
        if e.args[1] == Ack.NoTrk0:
            print(e, '- is the head stuck?')
        else:
            raise e


def step(usb, args):
    while args.repeat != 0:
        seek_with_catch_notrk0(usb, args.ecyl, args.wait)
        seek_with_catch_notrk0(usb, args.scyl, args.wait)
        args.repeat -= 1

def main(argv):

    parser = util.ArgumentParser()
    parser.add_argument("--drive", type=util.drive_letter, default='A',
                        help="drive to step (A,B,0,1,2)")
    parser.add_argument("--ecyl", type=int, default=81,
                        help="last cylinder in step range")
    parser.add_argument("--repeat", type=int, default=0,
                        help="times to repeat (0 = forever)")
    parser.add_argument("--wait", action='store_true',
                        help="wait for input between step cycles")
    parser.add_argument("device", nargs="?", default="auto",
                        help="serial device")
    parser.prog += ' ' + argv[1]
    args = parser.parse_args(argv[2:])
    args.scyl = 0
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
