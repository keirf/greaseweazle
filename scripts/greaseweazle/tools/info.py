# greaseweazle/tools/info.py
#
# Greaseweazle control script: Displat info about tools, firmware, and drive.
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

description = "Display information about the Greaseweazle setup."

import sys, serial

from greaseweazle.tools import util
from greaseweazle import usb as USB
from greaseweazle import version

def print_info_line(name, value, tab=0):
    print(''.ljust(tab) + (name + ':').ljust(12-tab) + value)

def main(argv):

    parser = util.ArgumentParser()
    parser.add_argument("device", nargs="?", default="auto",
                        help="serial device")
    parser.description = description
    parser.prog += ' ' + argv[1]
    args = parser.parse_args(argv[2:])

    print_info_line('Host Tools', 'v%d.%d' % (version.major, version.minor))

    print('Greaseweazle:')

    try:
        usb = util.usb_open(args.device, mode_check=False)
    except serial.SerialException:
        print('  Not found')
        sys.exit(0)

    port = usb.port_info
    if port.device:
        print_info_line('Device', port.device, tab=2)
    print_info_line('Model', 'F%d' % usb.hw_type, tab=2)
    fwver = 'v%d.%d' % (usb.major, usb.minor)
    if usb.update_mode:
        fwver += ' (Update Bootloader)'
    print_info_line('Firmware', fwver, tab=2)
    if port.serial_number:
        print_info_line('Serial', port.serial_number, tab=2)


if __name__ == "__main__":
    main(sys.argv)

# Local variables:
# python-indent: 4
# End:
