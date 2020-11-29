# greaseweazle/tools/util.py
#
# Greaseweazle control script: Utility functions.
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import argparse, os, sys, serial, struct, time
import importlib
import serial.tools.list_ports

from greaseweazle import version
from greaseweazle import error
from greaseweazle import usb as USB


class CmdlineHelpFormatter(argparse.ArgumentDefaultsHelpFormatter):
    def _get_help_string(self, action):
        help = action.help
        if '%no_default' in help:
            return help.replace('%no_default', '')
        if ('%(default)' in help
            or action.default is None
            or action.default is False
            or action.default is argparse.SUPPRESS):
            return help
        return help + ' (default: %(default)s)'


class ArgumentParser(argparse.ArgumentParser):
    def __init__(self, formatter_class=CmdlineHelpFormatter, *args, **kwargs):
        return super().__init__(formatter_class=formatter_class,
                                *args, **kwargs)

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


def split_opts(seq):
    """Splits a name from its list of options."""
    parts = seq.split('::')
    name, opts = parts[0], dict()
    for x in map(lambda x: x.split(':'), parts[1:]):
        for y in x:
            try:
                opt, val = y.split('=')
            except ValueError:
                opt, val = y, True
            if opt:
                opts[opt] = val
    return name, opts


def get_image_class(name):
    image_types = { '.adf': 'ADF',
                    '.scp': 'SCP',
                    '.hfe': 'HFE',
                    '.ipf': 'IPF' }
    _, ext = os.path.splitext(name)
    error.check(ext.lower() in image_types,
                "%s: Unrecognised file suffix '%s'" % (name, ext))
    typename = image_types[ext.lower()]
    mod = importlib.import_module('greaseweazle.image.' + typename.lower())
    return mod.__dict__[typename]


def with_drive_selected(fn, usb, args, *_args, **_kwargs):
    usb.set_bus_type(args.drive[0])
    try:
        usb.drive_select(args.drive[1])
        usb.drive_motor(args.drive[1], _kwargs.pop('motor', True))
        fn(usb, args, *_args, **_kwargs)
    except KeyboardInterrupt:
        print()
        usb.reset()
        usb.ser.close()
        usb.ser.open()
        raise
    finally:
        usb.drive_motor(args.drive[1], False)
        usb.drive_deselect()


def valid_ser_id(ser_id):
    return ser_id and ser_id.upper().startswith("GW")

def score_port(x, old_port=None):
    score = 0
    if x.manufacturer == "Keir Fraser" and x.product == "Greaseweazle":
        score = 20
    elif x.vid == 0x1209 and x.pid == 0x4d69:
        # Our very own properly-assigned PID. Guaranteed to be us.
        score = 20
    elif x.vid == 0x1209 and x.pid == 0x0001:
        # Our old shared Test PID. It's not guaranteed to be us.
        score = 10
    if score > 0 and valid_ser_id(x.serial_number):
        # A valid serial id is a good sign unless this is a reopen, and
        # the serials don't match!
        if not old_port or not valid_ser_id(old_port.serial_number):
            score = 20
        elif x.serial_number == old_port.serial_number:
            score = 30
        else:
            score = 0
    if old_port and old_port.location:
        # If this is a reopen, location field must match. A match is not
        # sufficient in itself however, as Windows may supply the same
        # location for multiple USB ports (this may be an interaction with
        # BitDefender). Hence we do not increase the port's score here.
        if not x.location or x.location != old_port.location:
            score = 0
    return score

def find_port(old_port=None):
    best_score, best_port = 0, None
    for x in serial.tools.list_ports.comports():
        score = score_port(x, old_port)
        if score > best_score:
            best_score, best_port = score, x
    if best_port:
        return best_port.device
    raise serial.SerialException('Cannot find the Greaseweazle device')

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


def usb_open(devicename, is_update=False, mode_check=True):

    if devicename is None:
        devicename = find_port()
    
    usb = USB.Unit(serial.Serial(devicename))
    usb.port_info = port_info(devicename)

    if not mode_check:
        return usb

    if usb.update_mode and not is_update:
        if usb.hw_model == 7 and not usb.update_jumpered:
            usb = usb_reopen(usb, is_update)
            if not usb.update_mode:
                return usb
        print("Greaseweazle is in Firmware Update Mode:")
        print(" The only available action is \"update\" of main firmware")
        if usb.update_jumpered:
            print(" Remove the Update Jumper for normal operation")
        else:
            print(" Main firmware is erased: You *must* perform an update!")
        sys.exit(1)

    if is_update and not usb.update_mode:
        if usb.hw_model == 7:
            usb = usb_reopen(usb, is_update)
            error.check(usb.update_mode, """\
Greaseweazle F7 did not change to Firmware Update Mode as requested.
If the problem persists, install the Update Jumper (across RX/TX).""")
            return usb
        print("Greaseweazle is in Normal Mode:")
        print(" To \"update\" you must install the Update Jumper")
        sys.exit(1)

    if not usb.update_mode and usb.update_needed:
        print("Firmware is out of date: Require v%u.%u"
              % (version.major, version.minor))
        if usb.hw_model == 7:
            print("Run \"update <update_file>\"")
        else:
            print("Install the Update Jumper and \"update <update_file>\"")
        sys.exit(1)

    return usb
    


# Local variables:
# python-indent: 4
# End:
