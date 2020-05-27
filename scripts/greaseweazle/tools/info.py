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

model_id = { 1: { 0: 'F1' },
             7: { 0: 'F7',
                  1: 'AmberTronic F7 Plus',
                  2: 'F7 Lightning' } }

speed_id = { 0: 'Full Speed (12 Mbit/s)',
             1: 'High Speed (480 Mbit/s)' }

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

    try:
        model = model_id[usb.hw_model][usb.hw_submodel]
    except KeyError:
        model = 'Unknown (0x%02X%02X)' % (usb.hw_model, usb.hw_submodel)
    print_info_line('Model', model, tab=2)

    fwver = 'v%d.%d' % (usb.major, usb.minor)
    if usb.update_mode:
        fwver += ' (Update Bootloader)'
    print_info_line('Firmware', fwver, tab=2)

    print_info_line('Serial', port.serial_number if port.serial_number
                    else 'Unknown', tab=2)

    try:
        speed = speed_id[usb.usb_speed]
    except KeyError:
        speed = 'Unknown (0x%02X)' % usb.usb_speed
    print_info_line('USB Rate', speed, tab=2)


if __name__ == "__main__":
    main(sys.argv)

# Local variables:
# python-indent: 4
# End:
