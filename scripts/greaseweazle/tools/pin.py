# greaseweazle/tools/pin.py
#
# Greaseweazle control script: Set a floppy interface pin to specified level.
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

description = "Change the setting of a user-modifiable interface pin."

import sys, argparse

from greaseweazle.tools import util
from greaseweazle import usb as USB

def level(letter):
    levels = { 'H': True, 'L': False }
    if not letter.upper() in levels:
        raise argparse.ArgumentTypeError("invalid pin level: '%s'" % letter)
    return levels[letter.upper()]

def main(argv):

    parser = util.ArgumentParser(usage='%(prog)s [options] pin level')
    parser.add_argument("--device", help="greaseweazle device name")
    parser.add_argument("pin", type=int, help="pin number")
    parser.add_argument("level", type=level, help="pin level (H,L)")
    parser.description = description
    parser.prog += ' ' + argv[1]
    args = parser.parse_args(argv[2:])

    try:
        usb = util.usb_open(args.device)
        usb.set_pin(args.pin, args.level)
        print("Pin %u is set %s" %
              (args.pin, ("Low (0v)", "High (5v)")[args.level]))
    except USB.CmdError as error:
        print("Command Failed: %s" % error)


if __name__ == "__main__":
    main(sys.argv)

# Local variables:
# python-indent: 4
# End:
