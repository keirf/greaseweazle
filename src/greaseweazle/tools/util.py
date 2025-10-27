# greaseweazle/tools/util.py
#
# Greaseweazle control script: Utility functions.
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from __future__ import annotations
from typing import Callable

import argparse, os, sys, serial, struct, time, re, platform
import importlib
from collections import OrderedDict
import itertools as it

if os.name == 'nt':
    from .list_ports_windows import comports # type: ignore
else:
    from serial.tools.list_ports import comports

from greaseweazle import error
from greaseweazle import usb as USB


def columnify(strings, columns=80, sep=2):
    max_len = max(len(s) for s in strings) + sep
    per_row = max(1, columns // max_len)
    return '\n'.join(map(lambda row: (f'{{:{max_len}}}'*per_row).format(*row),
                         it.zip_longest(*[iter(strings)]*per_row,
                                        fillvalue='')))


class CmdlineHelpFormatter(argparse.ArgumentDefaultsHelpFormatter,
                           argparse.RawDescriptionHelpFormatter):
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
                                allow_abbrev=False,
                                *args, **kwargs)

def min_int(_min):
    def x(value):
        ivalue = int(value)
        if ivalue < _min:
            raise argparse.ArgumentTypeError("must be %d or greater" % _min)
        return ivalue
    return x
uint = min_int(0)

def level(letter):
    levels = { 'H': True, 'L': False }
    if not letter.upper() in levels:
        raise argparse.ArgumentTypeError("invalid pin level: '%s'" % letter)
    return levels[letter.upper()]

drive_desc = """\
DRIVE: Drive (and bus) identifier:
  0 | 1 | 2 | 3       :: Shugart bus unit
  A | B               :: IBM/PC bus unit
"""

speed_desc = """\
SPEED: Track rotation time specified as:
  <N>rpm | <N>ms | <N>us | <N>ns | <N>scp | <N>
"""

tspec_desc = """\
TSPEC: Colon-separated list of:
  c=SET               :: Set of cylinders to access
  h=SET               :: Set of heads (sides) to access
  step=[0-9]          :: # physical head steps between cylinders
  hswap               :: Swap physical drive heads
  h[01].off=[+-][0-9] :: Physical cylinder offsets per head
  SET is a comma-separated list of integers and integer ranges
  e.g. 'c=0-7,9-12:h=0-1'
"""

pllspec_desc = """\
PLLSPEC: Colon-separated list of:
  period=PCT          :: Period adjustment as percentage of phase error
  phase=PCT           :: Phase adjustment as percentage of phase error
  lowpass=USEC        :: Filter flux periods shorter than USEC
  Defaults: period=5:phase=60 (no lowpass filter)
"""

precompspec_desc = """\
PRECOMP: Any of the following elements:
  type=<t>            :: Precomp type (mfm, fm, gcr): Default mfm
  <c>=<p>             :: Precompensate all cylinders >= c by p nanoseconds
  e.g. '40=125' to apply 125ns MFM precompensation to cylinders 40 and higher
"""

# Returns time period in seconds (float)
# Accepts rpm, ms, us, ns, scp. Naked value is assumed rpm.
def period(arg):
    m = re.match(r'(\d*\.\d+|\d+)rpm', arg)
    if m is not None:
        return 60 / float(m.group(1))
    m = re.match(r'(\d*\.\d+|\d+)ms', arg)
    if m is not None:
        return float(m.group(1)) / 1e3
    m = re.match(r'(\d*\.\d+|\d+)us', arg)
    if m is not None:
        return float(m.group(1)) / 1e6
    m = re.match(r'(\d*\.\d+|\d+)ns', arg)
    if m is not None:
        return float(m.group(1)) / 1e9
    m = re.match(r'(\d*\.\d+|\d+)scp', arg)
    if m is not None:
        return float(m.group(1)) / 40e6 # SCP @ 40MHz
    return 60 / float(arg)

class Drive:
    def __call__(self, letter: str) -> Drive:
        types = {
            'A': (USB.BusType.IBMPC, 0),
            'B': (USB.BusType.IBMPC, 1),
            '0': (USB.BusType.Shugart, 0),
            '1': (USB.BusType.Shugart, 1),
            '2': (USB.BusType.Shugart, 2),
            '3': (USB.BusType.Shugart, 3),
        }
        if not letter.upper() in types:
            raise argparse.ArgumentTypeError("invalid drive letter: '%s'"
                                             % letter)
        self.bus, self.unit_id = types[letter.upper()]
        return self

def range_str(l):
    if len(l) == 0:
        return '<none>'
    p, str = None, ''
    for i in l:
        if p is not None and i == p[1]+1:
            p = p[0], i
            continue
        if p is not None:
            str += ('%d,' % p[0]) if p[0] == p[1] else ('%d-%d,' % p)
        p = (i,i)
    if p is not None:
        str += ('%d' % p[0]) if p[0] == p[1] else ('%d-%d' % p)
    return str

class TrackSet:

    class TrackIter:
        """Iterate over a TrackSet in physical <cyl,head> order."""
        def __init__(self, ts):
            l = []
            for c in ts.cyls:
                for h in ts.heads:
                    pc, ph = ts.ch_to_pch(c, h)
                    l.append((pc, ph, c, h))
            l.sort()
            self.l = iter(l)
        def __next__(self):
            (self.physical_cyl, self.physical_head,
             self.cyl, self.head) = next(self.l)
            return self
    
    def __init__(self, trackspec):
        self.cyls = list()
        self.heads = list()
        self.h_off = [0]*2
        self.step = 1
        self.hswap = False
        self.trackspec = ''
        self.update_from_trackspec(trackspec)

    def ch_to_pch(self, c, h):
        pc = c//-self.step if self.step < 0 else c*self.step
        pc += self.h_off[h]
        ph = 1-h if self.hswap else h
        return pc, ph

    def update_from_trackspec(self, trackspec):
        """Update a TrackSet based on a trackspec."""
        self.trackspec += trackspec
        for x in trackspec.split(':'):
            if x == 'hswap':
                self.hswap = True
                continue
            k,v = x.split('=')
            if k == 'c':
                cyls = set()
                for crange in v.split(','):
                    m = re.match(r'(\d+)(-(\d+)(/(\d+))?)?$', crange)
                    if m is None: raise ValueError()
                    if m.group(3) is None:
                        s,e,step = int(m.group(1)), int(m.group(1)), 1
                    else:
                        s,e,step = int(m.group(1)), int(m.group(3)), 1
                        if m.group(5) is not None:
                            step = int(m.group(5))
                    for c in range(s, e+1, step):
                        cyls.add(c)
                self.cyls = sorted(cyls)
            elif k == 'h':
                heads = [False]*2
                for hrange in v.split(','):
                    m = re.match(r'([01])(-([01]))?$', hrange)
                    if m is None: raise ValueError()
                    if m.group(3) is None:
                        s,e = int(m.group(1)), int(m.group(1))
                    else:
                        s,e = int(m.group(1)), int(m.group(3))
                    for h in range(s, e+1):
                        heads[h] = True
                self.heads = []
                for h in range(len(heads)):
                    if heads[h]: self.heads.append(h)
            elif re.match(r'h[01].off$', k):
                h = int(re.match(r'h([01]).off$', k).group(1))
                m = re.match(r'([+-]\d+)$', v)
                if m is None: raise ValueError()
                self.h_off[h] = int(m.group(1))
            elif k == 'step':
                m = re.match(r'1/(\d+)$', v)
                self.step = -int(m.group(1)) if m is not None else int(v)
            else:
                raise ValueError()
        
    def __str__(self):
        s = 'c=%s' % range_str(self.cyls)
        s += ':h=%s' % range_str(self.heads)
        for i in range(len(self.h_off)):
            x = self.h_off[i]
            if x != 0:
                s += ':h%d.off=%s%d' % (i, '+' if x >= 0 else '', x)
        if self.step != 1:
            s += ':step=' + (('1/%d' % -self.step) if self.step < 0
                             else ('%d' % self.step))
        if self.hswap: s += ':hswap'
        return s

    def __iter__(self):
        return self.TrackIter(self)

    def __contains__(self, key):
        c, h = key
        return c in self.cyls and h in self.heads

def split_opts(seq):
    """Splits a name from its list of options."""
    parts = seq.split('::')
    name, opts = parts[0], dict()
    for x in map(lambda x: x.split(':'), parts[1:]):
        for y in x:
            try:
                opt, val = y.split('=')
            except ValueError:
                opt, val = y, 'yes'
            if opt:
                opts[opt] = val
    return name, opts


image_types = OrderedDict(
    { '.a2r': 'A2R',
      '.adf': 'ADF',
      '.ads': ('ADS','acorn'),
      '.adm': ('ADM','acorn'),
      '.adl': ('ADL','acorn'),
      '.ctr': ('CTRaw','caps'),
      '.d1m': ('D1M','d81'),
      '.d2m': ('D2M','d81'),
      '.d4m': ('D4M','d81'),
      '.d64': 'D64',
      '.d71': ('D71','d64'),
      '.d81': 'D81',
      '.d88': 'D88',
      '.dcp': 'DCP',
      '.dim': 'DIM',
      '.dmk': 'DMK',
      '.do' : ('DO','apple2'),
      '.dsd': ('DSD','acorn'),
      '.dsk': 'DSK',
      '.edsk': 'EDSK',
      '.fd':  'FD',
      '.fdi': 'FDI',
      '.hdm': 'HDM',
      '.hfe': 'HFE',
      '.ima': 'IMG',
      '.img': 'IMG',
      '.imd': 'IMD',
      '.ipf': ('IPF','caps'),
      '.mgt': 'MGT',
      '.msa': 'MSA',
      '.nfd': 'NFD',
      '.nsi': 'NSI',
      '.po' : ('PO','apple2'),
      '.raw': 'KryoFlux',
      '.sf7': 'SF7',
      '.scp': 'SCP',
      '.ssd': ('SSD','acorn'),
      '.st' : 'IMG',
      '.td0': 'TD0',
      '.xdf': 'XDF' })

def get_image_class(name):
    _, ext = os.path.splitext(name)
    error.check(ext.lower() in image_types,
                "%s: Unrecognised file suffix '%s'\nKnown suffixes:\n%s"
                % (name, ext, columnify(image_types)))
    typespec = image_types[ext.lower()]
    if isinstance(typespec, tuple):
        typename, classname = typespec
    else:
        typename, classname = typespec, typespec.lower()
    mod = importlib.import_module('greaseweazle.image.' + classname)
    return mod.__dict__[typename]


def with_drive_selected(
        fn: Callable[[],None],
        usb: USB.Unit,
        drive: Drive,
        motor: bool = True
):
    try:
        usb.set_bus_type(drive.bus.value)
    except USB.CmdError as err:
        if err.code == USB.Ack.BadCommand:
            raise error.Fatal("Device does not support " + str(drive.bus))
        raise
    try:
        usb.drive_select(drive.unit_id)
        usb.drive_motor(drive.unit_id, motor)
        fn()
    except KeyboardInterrupt:
        print()
        usb.reset()
        raise
    finally:
        usb.drive_motor(drive.unit_id, False)
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
    elif x.product and "gw-compat" in x.product.lower():
        # Device self-reports as "Greaseweazle compatible" via its product
        # string. Let's judge it not *quite* as good as the real thing. ;)
        score = 19
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
    for x in comports():
        score = score_port(x, old_port)
        if score > best_score:
            best_score, best_port = score, x
    if best_port:
        return best_port.device
    raise serial.SerialException('Cannot find the Greaseweazle device')

def port_info(devname):
    for x in comports():
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
            new_usb.jumperless_update = usb.jumperless_update
            new_usb.can_mode_switch = usb.can_mode_switch
            return new_usb
    raise serial.SerialException('''\
Could not find the Greaseweazle device after switching firmware mode.
If you are connected via a USB hub, instead try connecting directly.''')


def print_update_instructions(usb):
    print("To perform an Update:")
    if not usb.jumperless_update:
        print(" - Disconnect from USB")
        print(" - Install the Update Jumper at pins %s"
              % ("RXI-TXO" if usb.hw_model != 1 else "DCLK-GND"))
        print(" - Reconnect to USB")
    print(" - Run \"gw update\" to download and install latest firmware")


def usb_mode_check(usb, is_update):

    if usb.update_mode and not is_update:
        if usb.can_mode_switch:
            usb = usb_reopen(usb, is_update)
            if not usb.update_mode:
                return usb
        print("ERROR: Device is in Firmware Update Mode")
        print(" - The only available action is \"gw update\"")
        if usb.update_jumpered:
            print(" - For normal operation disconnect from USB and remove "
                  "the Update Jumper at pins %s"
                  % ("RXI-TXO" if usb.hw_model != 1 else "DCLK-GND"))
        else:
            print(" - Main firmware is erased: You *must* perform an update!")
        sys.exit(1)

    if is_update and not usb.update_mode:
        if usb.can_mode_switch:
            usb = usb_reopen(usb, is_update)
            error.check(usb.update_mode, """\
Device did not change to Firmware Update Mode as requested.
If the problem persists, install the Update Jumper at pins RXI-TXO.""")
            return usb
        print("ERROR: Device is not in Firmware Update Mode")
        print_update_instructions(usb)
        sys.exit(1)

    if not usb.update_mode and usb.update_needed:
        print("ERROR: Device firmware version %u.%u is unsupported"
              % (usb.major, usb.minor))
        print_update_instructions(usb)
        sys.exit(1)

    return usb


def usb_open(devicename, is_update=False, mode_check=True):

    if devicename is None:
        devicename = find_port()
    
    usb = USB.Unit(serial.Serial(devicename))
    usb.port_info = port_info(devicename)
    is_win7 = (platform.system() == 'Windows' and platform.release() == '7')
    usb.jumperless_update = ((usb.hw_model, usb.hw_submodel) != (1, 0)
                             and not is_win7)
    usb.can_mode_switch = (usb.jumperless_update
                           and not (usb.update_mode and usb.update_jumpered))

    if mode_check:
        usb = usb_mode_check(usb, is_update)

    return usb
    


# Local variables:
# python-indent: 4
# End:
