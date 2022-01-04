# greaseweazle/tools/read.py
#
# Greaseweazle control script: Read Disk to Image.
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

description = "Measure RPM of drive spindle."

from greaseweazle.tools import util
from greaseweazle import usb as USB

def print_rpm(usb, args):
    """Prints spindle RPM.
    """

    for _ in range(args.nr):
        flux = usb.read_track(1)
        time_per_rev = flux.index_list[-1] / flux.sample_freq
        print("Rate: %.2f rpm ; Period: %.2f ms"
              % (60 / time_per_rev, time_per_rev * 1e3))


def main(argv):

    parser = util.ArgumentParser(usage='%(prog)s [options]')
    parser.add_argument("--device", help="greaseweazle device name")
    parser.add_argument("--drive", type=util.drive_letter, default='A',
                        help="drive to read (A,B,0,1,2)")
    parser.add_argument("--nr", type=int, default=1,
                        help="number of iterations")
    parser.description = description
    parser.prog += ' ' + argv[1]
    args = parser.parse_args(argv[2:])

    try:
        usb = util.usb_open(args.device)
        util.with_drive_selected(print_rpm, usb, args)
    except USB.CmdError as err:
        print("Command Failed: %s" % err)


# Local variables:
# python-indent: 4
# End:
