#!/usr/bin/env python3

# gw.py
#
# Greaseweazle control script.
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import sys
import importlib

missing_modules = []

try:
    import bitarray
except ImportError:
    missing_modules.append("bitarray")
    
try:
    import crcmod
except ImportError:
    missing_modules.append("crcmod")
    
try:
    import serial.tools.list_ports
except ImportError:
    missing_modules.append("pyserial")

if missing_modules:
    print("""\
** Missing Python modules: %s
For installation instructions please read the wiki:
<https://github.com/keirf/Greaseweazle/wiki/Software-Installation>"""
          % ', '.join(missing_modules))
    sys.exit(1)

actions = [ 'info',
            'read',
            'write',
            'erase',
            'delays',
            'update',
            'pin',
            'reset',
            'bandwidth' ]
argv = sys.argv

backtrace = False
if len(argv) > 1 and argv[1] == '--bt':
    backtrace = True
    argv = [argv[0]] + argv[2:]

if len(argv) < 2 or argv[1] not in actions:
    print("Usage: %s [action] [-h] ..." % (argv[0]))
    print("  -h, --help  Show help message for specified action")
    print("Actions:")
    for a in actions:
        mod = importlib.import_module('greaseweazle.tools.' + a)
        print('  %-12s%s' % (a, mod.__dict__['description']))
    sys.exit(1)

mod = importlib.import_module('greaseweazle.tools.' + argv[1])
main = mod.__dict__['main']
try:
    res = main(argv)
    if res is None:
        res = 0
except (IndexError, AssertionError, TypeError, KeyError):
    raise
except KeyboardInterrupt:
    if backtrace: raise
    res = 1
except Exception as err:
    if backtrace: raise
    print("** FATAL ERROR:")
    print(err)
    res = 1
sys.exit(res)
    
# Local variables:
# python-indent: 4
# End:
