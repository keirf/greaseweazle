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

actions = [ 'read', 'write', 'delays', 'update' ]
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
