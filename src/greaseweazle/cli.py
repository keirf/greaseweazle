# cli.py
#
# Greaseweazle command line interface.
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import sys, time, struct, textwrap
import importlib

from greaseweazle import __version__

actions = [ 'info',
            'read',
            'write',
            'convert',
            'erase',
            'clean',
            'seek',
            'delays',
            'update',
            'pin',
            'reset',
            'bandwidth',
            'rpm' ]

def usage(argv):
    print("Usage: %s [--time] [--stdout] [action] [-h] ..." % (argv[0]))
    print("  --time      Print elapsed time after action is executed")
    print("  --stdout    Log progress to stdout instead of stderr")
    print("  -h, --help  Show help message for specified action")
    print("Actions:")
    for a in actions:
        mod = importlib.import_module('greaseweazle.tools.' + a)
        print('  %-12s%s' % (a, mod.__dict__['description']))
    return 1

def main():
    argv = sys.argv
    backtrace = False
    start_time = None
    use_stdout = False

    while len(argv) > 1 and argv[1].startswith('--'):
        if argv[1] == '--bt':
            backtrace = True
        elif argv[1] == '--time':
            start_time = time.time()
        elif argv[1] == '--stdout':
            use_stdout = True
        else:
            return usage(argv)
        argv = [argv[0]] + argv[2:]

    if len(argv) < 2 or argv[1] not in actions:
        return usage(argv)

    # All logging/printing on stderr. This keeps stdout clean for future use.
    # User can specify `--stdout' if he/she needs progress logged to stdout anyway.
    # Configure line buffering, even if the logging output is not to a console.
    if use_stdout == False:
        sys.stderr.reconfigure(line_buffering=True)
        sys.stdout = sys.stderr

    if '+' in __version__:
        print("""*** TEST/PRE-RELEASE: %s
*** Use these tools ONLY for test and development!!"""
              % __version__)

    mod = importlib.import_module('greaseweazle.tools.' + argv[1])
    main = mod.__dict__['main']
    try:
        res = main(argv)
        if res is None:
            res = 0
    except (IndexError, AssertionError, TypeError, KeyError, struct.error):
        raise
    except KeyboardInterrupt:
        if backtrace: raise
        res = 1
    except Exception as err:
        if backtrace: raise
        print("** FATAL ERROR:")
        print(textwrap.dedent(str(err)))
        res = 1

    if start_time is not None:
        elapsed = time.time() - start_time
        print("Time elapsed: %.2f seconds" % elapsed)

    return res

# Local variables:
# python-indent: 4
# End:
