# greaseweazle/tools/reset.py
#
# Greaseweazle control script: Reset to power-on defaults.
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

description = "Reset the Greaseweazle device to power-on default state."

import sys

from greaseweazle.tools import util
from greaseweazle.tools.delays import Delays
from greaseweazle import usb as USB

def main(argv) -> None:

    parser = util.ArgumentParser(usage='%(prog)s [options]')
    parser.add_argument("--device", help="device name (COM/serial port)")
    parser.add_argument("--delays", action="store_true",
                        help="include \"gw delays\" in the reset")
    parser.description = description
    parser.prog += ' ' + argv[1]
    args = parser.parse_args(argv[2:])

    try:
        usb = util.usb_open(args.device)
        delays = Delays(usb)
        usb.power_on_reset()
        if not args.delays:
            delays.update()
    except USB.CmdError as error:
        print("Command Failed: %s" % error)


if __name__ == "__main__":
    main(sys.argv)

# Local variables:
# python-indent: 4
# End:
