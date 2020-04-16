# greaseweazle/tools/util.py
#
# Greaseweazle control script: Utility functions.
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import argparse, os, sys, serial, struct, time
import serial.tools.list_ports

from greaseweazle import version
from greaseweazle import usb as USB
from greaseweazle.image.scp import SCP
from greaseweazle.image.hfe import HFE
from greaseweazle.image.ipf import IPF


def drive_letter(letter):
    types = {
        'A': (USB.BusType.IBMPC, 0),
        'B': (USB.BusType.IBMPC, 1),
        '0': (USB.BusType.Shugart, 0),
        '1': (USB.BusType.Shugart, 1),
        '2': (USB.BusType.Shugart, 2)
    }
    if not letter.upper() in types:
        raise argparse.ArgumentTypeError("invalid drive letter: '%s'" % letter)
    return types[letter.upper()]


def get_image_class(name):
    image_types = { '.scp': SCP, '.hfe': HFE, '.ipf': IPF }
    _, ext = os.path.splitext(name)
    if not ext.lower() in image_types:
        print("%s: Unrecognised file suffix '%s'" % (name, ext))
        return None
    return image_types[ext.lower()]


def with_drive_selected(fn, usb, args):
    usb.set_bus_type(args.drive[0])
    try:
        usb.drive_select(args.drive[1])
        usb.drive_motor(args.drive[1], True)
        fn(usb, args)
    except KeyboardInterrupt:
        print()
        usb.reset()
        usb.ser.close()
        usb.ser.open()
    finally:
        usb.drive_motor(args.drive[1], False)
        usb.drive_deselect()


def valid_ser_id(ser_id):
    return ser_id and ser_id.upper().startswith("GW")

def find_port(old_port=None):
    # If we are reopening, and we know the location of the old port, require
    # to match on location.
    if old_port and old_port.location:
        for x in serial.tools.list_ports.comports():
            if x.location and x.location == old_port.location:
                return x.device
        return None
    # Score each serial port
    best_score, best_port = 0, None
    for x in serial.tools.list_ports.comports():
        score = 0
        if x.manufacturer == "Keir Fraser" and x.product == "Greaseweazle":
            score = 20
        elif x.vid == 0x1209 and x.pid == 0x0001:
            score = 10
        if score > 0 and valid_ser_id(x.serial_number):
            if not old_port or not valid_ser_id(old_port.serial_number):
                score = 20
            elif x.serial_number == old_port.serial_number:
                score = 30
            else:
                score = 0
        if score > best_score:
            best_score, best_port = score, x
    if best_port:
        return best_port.device
    raise serial.SerialException('Could not auto-probe Greaseweazle device')

def port_info(devname):
    for x in serial.tools.list_ports.comports():
        if x.device == devname:
            return x
    return None

def usb_reopen(usb, is_update):
    mode = { False: 1, True: 0 }
    try:
        usb.switch_fw_mode(mode[is_update])
    except (serial.SerialException, struct.error):
        # Mac and Linux raise SerialException ("... returned no data")
        # Win10 pyserial returns a short read which fails struct.unpack
        pass
    usb.ser.close()
    for i in range(10):
        time.sleep(0.5)
        try:
            devicename = find_port(usb.port_info)
            new_ser = serial.Serial(devicename)
        except serial.SerialException:
            # Device not found
            pass
        else:
            new_usb = USB.Unit(new_ser)
            new_usb.port_info = port_info(devicename)
            return new_usb
    raise serial.SerialException('Could not reopen port after mode switch')


def usb_open(devicename, is_update=False):

    if devicename == "auto":
        devicename = find_port()
    
    usb = USB.Unit(serial.Serial(devicename))
    usb.port_info = port_info(devicename)

    print("** %s v%u.%u [F%u], Host Tools v%u.%u"
          % (("Greaseweazle", "Bootloader")[usb.update_mode],
             usb.major, usb.minor, usb.hw_type,
             version.major, version.minor))

    if usb.update_mode and not is_update:
        if usb.hw_type == 7 and not usb.update_jumpered:
            usb = usb_reopen(usb, is_update)
            if not usb.update_mode:
                return usb
        print("Greaseweazle is in Firmware Update Mode:")
        print(" The only available action is \"update <update_file>\"")
        if usb.update_jumpered:
            print(" Remove the Update Jumper for normal operation")
        else:
            print(" Main firmware is erased: You *must* perform an update!")
        sys.exit(1)

    if is_update and not usb.update_mode:
        if usb.hw_type == 7:
            return usb_reopen(usb, is_update)
        print("Greaseweazle is in Normal Mode:")
        print(" To \"update\" you must install the Update Jumper")
        sys.exit(1)

    if not usb.update_mode and usb.update_needed:
        print("Firmware is out of date: Require v%u.%u"
              % (version.major, version.minor))
        if usb.hw_type == 7:
            print("Run \"update <update_file>\"")
        else:
            print("Install the Update Jumper and \"update <update_file>\"")
        sys.exit(1)

    return usb
    


# Local variables:
# python-indent: 4
# End:
