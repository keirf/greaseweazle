# greaseweazle/optimised/__init__.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import os

gw_opt = os.environ.get('GW_OPT')
enabled = gw_opt is None or gw_opt.lower().startswith('y')
if enabled:
    try:
        from .optimised import *
    except ModuleNotFoundError:
        enabled = False
        print('*** WARNING: Optimised data routines not found: '
              'Run scripts/setup.sh')
else:
    print('*** WARNING: Optimised data routines disabled (GW_OPT=%s)'
          % gw_opt)

# Local variables:
# python-indent: 4
# End:
