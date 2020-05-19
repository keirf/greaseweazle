# greaseweazle/tools/delays.py
#
# Greaseweazle control script: Get/Set Delay Timers.
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

description = "Display (and optionally modify) Greaseweazle \
drive-delay parameters."

import sys

from greaseweazle.tools import util
from greaseweazle import usb as USB

def main(argv):

    parser = util.ArgumentParser()
    parser.add_argument("--select", type=int,
                        help="delay after drive select (usecs)")
    parser.add_argument("--step", type=int,
                        help="delay between head steps (usecs)")
    parser.add_argument("--settle", type=int,
                        help="settle delay after seek (msecs)")
    parser.add_argument("--motor", type=int,
                        help="delay after motor on (msecs)")
    parser.add_argument("--auto-off", type=int,
                        help="quiescent time until auto deselect (msecs)")
    parser.add_argument("device", nargs="?", default="auto",
                        help="serial device")
    parser.description = description
    parser.prog += ' ' + argv[1]
    args = parser.parse_args(argv[2:])

    try:

        usb = util.usb_open(args.device)

        if args.select:
            usb.select_delay = args.select
        if args.step:
            usb.step_delay = args.step
        if args.settle:
            usb.seek_settle_delay = args.settle
        if args.motor:
            usb.motor_delay = args.motor
        if args.auto_off:
            usb.auto_off_delay = args.auto_off

        print("Select Delay: %uus" % usb.select_delay)
        print("Step Delay: %uus" % usb.step_delay)
        print("Settle Time: %ums" % usb.seek_settle_delay)
        print("Motor Delay: %ums" % usb.motor_delay)
        print("Auto Off: %ums" % usb.auto_off_delay)

    except USB.CmdError as error:
        print("Command Failed: %s" % error)


if __name__ == "__main__":
    main(sys.argv)

# Local variables:
# python-indent: 4
# End:
