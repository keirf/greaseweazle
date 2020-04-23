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
except ModuleNotFoundError:
    missing_modules.append("bitarray")
    
try:
    import crcmod
except ModuleNotFoundError:
    missing_modules.append("crcmod")
    
try:
    import serial.tools.list_ports
except ModuleNotFoundError:
    missing_modules.append("pyserial")

if missing_modules:
    print("""\
** Missing Python modules: %s
For installation instructions please read the wiki:
<https://github.com/keirf/Greaseweazle/wiki/Software-Installation>"""
          % ', '.join(missing_modules))
    sys.exit(1)

actions = [ 'read', 'write', 'delays', 'update', 'pin', 'reset' ]
argv = sys.argv

if len(argv) < 2 or argv[1] not in actions:
    print("Usage: %s [action] ..." % (argv[0]))
    print("Actions: ", end="")
    print(", ".join(str(x) for x in actions))
    sys.exit(1)

mod = importlib.import_module('greaseweazle.tools.' + argv[1])
main = mod.__dict__['main']
res = main(argv)
if res is None:
    res = 0
sys.exit(res)
    
# Local variables:
# python-indent: 4
# End:
