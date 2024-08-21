# greaseweazle/tools/info.py
#
# Greaseweazle control script: Displat info about tools, firmware, and drive.
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

description = "Display information about the Greaseweazle setup."

from typing import Tuple

import requests, re
import sys, serial

from greaseweazle.tools import util
from greaseweazle import usb as USB
from greaseweazle import __version__

model_id = { 1: { 0: 'F1',
                  1: 'F1 Plus',
                  2: 'F1 Plus (Unbuffered)' },
             4: { 0: 'V4',
                  1: 'V4 Slim',
                  2: 'V4.1' },
             7: { 0: 'F7 v1',
                  1: 'F7 Plus (Ant Goffart, v1)',
                  2: 'F7 Lightning',
                  3: 'F7 v2)',
                  4: 'F7 Plus (Ant Goffart, v2)',
                  5: 'F7 Lightning Plus',
                  6: 'F7 Slim',
                  7: 'F7 v3 "Thunderbolt"' },
             8: { 0: 'Adafruit Floppy Generic' } }

speed_id = { 0: 'Full Speed (12 Mbit/s)',
             1: 'High Speed (480 Mbit/s)' }

mcu_id = { 2: 'AT32F403',
           7: 'AT32F403A',
           5: 'AT32F415' }

def print_info_line(name: str, value: str, tab=0) -> None:
    print(''.ljust(tab) + (name + ':').ljust(12-tab) + value)

def latest_firmware() -> Tuple[int,int]:
    rsp = requests.get('https://api.github.com/repos/keirf/'
                       'greaseweazle-firmware/releases/latest', timeout=5)
    if int(rsp.headers.get('X-RateLimit-Remaining', 1)) == 0:
        raise requests.RequestException('GitHub API Rate Limit exceeded')
    tag = rsp.json()['tag_name']
    r = re.match(r'v(\d+)\.(\d+)', tag)
    assert r is not None
    major, minor = int(r.group(1)), int(r.group(2))
    return major, minor

def main(argv) -> None:

    parser = util.ArgumentParser(usage='%(prog)s [options]')
    parser.add_argument("--device", help="device name (COM/serial port)")
    parser.add_argument("--bootloader", action="store_true",
                        help="display bootloader info (F7 only)")
    parser.description = description
    parser.prog += ' ' + argv[1]
    args = parser.parse_args(argv[2:])

    print_info_line('Host Tools', '%s' % __version__)

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
        if usb.hw_model != 8:
            model = 'Greaseweazle ' + model
    except KeyError:
        model = 'Unknown (0x%02X%02X)' % (usb.hw_model, usb.hw_submodel)
    print_info_line('Model', model, tab=2)

    mcu_strs = list()
    try:
        mcu_strs.append(mcu_id[usb.mcu_id])
    except KeyError:
        if usb.mcu_id != 0:
            mcu_strs.append('Unknown (0x%02X)' % usb.mcu_id)
    if usb.mcu_mhz:
        mcu_strs.append(f'{usb.mcu_mhz}MHz')
    if usb.mcu_sram_kb:
        mcu_strs.append(f'{usb.mcu_sram_kb}kB SRAM')
    if mcu_strs:
        print_info_line('MCU', ', '.join(mcu_strs), tab=2)

    fwver = '%d.%d' % usb.version
    if usb.update_mode:
        fwver += ' (Bootloader)'
    print_info_line('Firmware', fwver, tab=2)

    print_info_line('Serial', port.serial_number if port.serial_number
                    else 'Unknown', tab=2)

    usb_strs = list()
    try:
        usb_strs.append(speed_id[usb.usb_speed])
    except KeyError:
        usb_strs.append('Unknown (0x%02X)' % usb.usb_speed)
    if usb.usb_buf_kb:
        usb_strs.append(f'{usb.usb_buf_kb}kB Buffer')
    if usb_strs:
        print_info_line('USB', ', '.join(usb_strs), tab=2)

    usb_update_mode, usb_version = usb.update_mode, usb.version

    if mode_switched:
        usb = util.usb_reopen(usb, not args.bootloader)

    if not usb_update_mode:
        latest_version = latest_firmware()
        if latest_version > usb_version:
            print('\n*** New firmware version %d.%d is available'
                  % latest_version)
            util.print_update_instructions(usb)


if __name__ == "__main__":
    main(sys.argv)

# Local variables:
# python-indent: 4
# End:
