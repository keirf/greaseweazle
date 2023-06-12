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

def speed_str(tpr: float) -> str:
    return "Rate: %.3f rpm ; Period: %.3f ms" % (60 / tpr, tpr * 1e3)

def print_rpm(usb: USB.Unit, args) -> None:
    """Prints spindle RPM.
    """

    time_per_rev = list()

    try:
        for _ in range(args.nr):
            flux = usb.read_track(1)
            tpr = flux.index_list[-1] / flux.sample_freq
            time_per_rev.append(tpr)
            print(speed_str(tpr))
    finally:
        if len(time_per_rev) > 1:
            mean = sum(time_per_rev)/len(time_per_rev)
            median = sorted(time_per_rev)[len(time_per_rev)//2]
            print("***")
            print("FASTEST:  " + speed_str(min(time_per_rev)))
            print("Ar.Mean:  " + speed_str(mean))
            print("Median:   " + speed_str(median))
            print("SLOWEST:  " + speed_str(max(time_per_rev)))


def main(argv) -> None:

    epilog = (util.drive_desc)
    parser = util.ArgumentParser(usage='%(prog)s [options]',
                                 epilog=epilog)
    parser.add_argument("--device", help="greaseweazle device name")
    parser.add_argument("--drive", type=util.Drive(), default='A',
                        help="drive to read")
    parser.add_argument("--nr", type=util.uint, default=1, metavar="N",
                        help="number of iterations")
    parser.description = description
    parser.prog += ' ' + argv[1]
    args = parser.parse_args(argv[2:])

    try:
        usb = util.usb_open(args.device)
        util.with_drive_selected(lambda: print_rpm(usb, args), usb, args.drive)
    except USB.CmdError as err:
        print("Command Failed: %s" % err)


# Local variables:
# python-indent: 4
# End:
