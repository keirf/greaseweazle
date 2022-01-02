# greaseweazle/tools/info.py
#
# Greaseweazle control script: Displat info about tools, firmware, and drive.
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

description = "Display information about the Greaseweazle setup."

import requests, re
import sys, serial

from greaseweazle.tools import util
from greaseweazle import usb as USB
from greaseweazle import version

model_id = { 1: { 0: 'F1',
                  1: 'F1 Plus',
                  2: 'F1 Plus (Unbuffered)' },
             4: { 0: 'V4',
                  1: 'V4 Slim' },
             7: { 0: 'F7 v1',
                  1: 'F7 Plus (Ant Goffart, v1)',
                  2: 'F7 Lightning',
                  3: 'F7 v2)',
                  4: 'F7 Plus (Ant Goffart, v2)',
                  5: 'F7 Lightning Plus',
                  6: 'F7 Slim',
                  7: 'F7 v3 "Thunderbolt"' },
             8: { 0: 'Adafruit Floppy Generic',}
             }

speed_id = { 0: 'Full Speed (12 Mbit/s)',
             1: 'High Speed (480 Mbit/s)' }

def print_info_line(name, value, tab=0):
    print(''.ljust(tab) + (name + ':').ljust(12-tab) + value)

def latest_firmware():
    rsp = requests.get('https://api.github.com/repos/keirf/'
                       'greaseweazle-firmware/releases/latest', timeout=5)
    tag = rsp.json()['tag_name']
    r = re.match(r'v(\d+)\.(\d+)', tag)
    major, minor = int(r.group(1)), int(r.group(2))
    return major, minor

def main(argv):

    parser = util.ArgumentParser(usage='%(prog)s [options]')
    parser.add_argument("--device", help="greaseweazle device name")
    parser.add_argument("--bootloader", action="store_true",
                        help="display bootloader info (F7 only)")
    parser.description = description
    parser.prog += ' ' + argv[1]
    args = parser.parse_args(argv[2:])

    print_info_line('Host Tools', 'v%d.%d' % (version.major, version.minor))

    print('Device:')

    try:
        usb = util.usb_open(args.device, mode_check=False)
    except serial.SerialException:
        print('  Not found')
        sys.exit(0)

    mode_switched = usb.can_mode_switch and usb.update_mode != args.bootloader
    if mode_switched:
        usb = util.usb_reopen(usb, args.bootloader)
        
    port = usb.port_info

    if port.device:
        print_info_line('Port', port.device, tab=2)

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

    usb_update_mode, usb_version = usb.update_mode, usb.version

    if mode_switched:
        usb = util.usb_reopen(usb, not args.bootloader)

    if not usb_update_mode:
        latest_version = latest_firmware()
        if latest_version > usb_version:
            print('\n*** New firmware v%d.%d is available' % latest_version)
            util.print_update_instructions(usb)


if __name__ == "__main__":
    main(sys.argv)

# Local variables:
# python-indent: 4
# End:
