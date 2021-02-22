#!/usr/bin/env python3

# gw.py
#
# Greaseweazle control script.
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import sys, time
import importlib

from greaseweazle import version
if hasattr(version, 'commit'):
    print("""*** TEST/PRE-RELEASE: commit %s
*** Use these tools and firmware ONLY for test and development!!"""
          % version.commit)

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
            'clean',
            'seek',
            'delays',
            'update',
            'pin',
            'reset',
            'bandwidth' ]
argv = sys.argv

def usage():
    print("Usage: %s [--time] [action] [-h] ..." % (argv[0]))
    print("  --time      Print elapsed time after action is executed")
    print("  -h, --help  Show help message for specified action")
    print("Actions:")
    for a in actions:
        mod = importlib.import_module('greaseweazle.tools.' + a)
        print('  %-12s%s' % (a, mod.__dict__['description']))
    sys.exit(1)

backtrace = False
start_time = None

while len(argv) > 1 and argv[1].startswith('--'):
    if argv[1] == '--bt':
        backtrace = True
    elif argv[1] == '--time':
        start_time = time.time()
    else:
        usage()
    argv = [argv[0]] + argv[2:]

if len(argv) < 2 or argv[1] not in actions:
    usage()

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

if start_time is not None:
    elapsed = time.time() - start_time
    print("Time elapsed: %.2f seconds" % elapsed)

sys.exit(res)
    
# Local variables:
# python-indent: 4
# End:
