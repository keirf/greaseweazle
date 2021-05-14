# greaseweazle/tools/getpin.py
#
# Greaseweazle control script: Get the value of a floppy interface pin.
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

description = "Get the setting of an interface pin."

import sys, argparse

from greaseweazle.tools import util
from greaseweazle import usb as USB

def main(argv):

    parser = util.ArgumentParser(usage='%(prog)s [options] pin')
    parser.add_argument("--device", help="greaseweazle device name")
    parser.add_argument("--drive", type=util.drive_letter, default='A',
                        help="drive to read (A,B,0,1,2)")
    parser.add_argument("pin", type=int, help="pin number")
    parser.description = description
    parser.prog += ' ' + argv[1]
    args = parser.parse_args(argv[2:])

    try:
        usb = util.usb_open(args.device)
#        usb.set_bus_type(args.drive[0])
        usb.drive_select(args.drive[1])
        value = usb.get_pin(args.pin)
        print("Pin %u is %s" %
             (args.pin, ("Low (0v)", "High (5v)")[value]))
    except USB.CmdError as error:
        print("Command Failed: %s" % error)

    usb.drive_deselect()

if __name__ == "__main__":
    main(sys.argv)

# Local variables:
# python-indent: 4
# End:
