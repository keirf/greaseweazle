# greaseweazle/tools/erase.py
#
# Greaseweazle control script: Erase a Disk.
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

description = "Erase a disk."

import sys

from greaseweazle import error
from greaseweazle.tools import util
from greaseweazle import usb as USB

def erase(usb: USB.Unit, args) -> None:

    # @drive_ticks is the time in Greaseweazle ticks between index pulses.
    # We will adjust the flux intervals per track to allow for this.
    if args.fake_index is not None:
        drive_ticks = args.fake_index * usb.sample_freq
    else:
        drive_ticks = usb.read_track(2).ticks_per_rev

    for t in args.tracks:
        print('T%u.%u: Erasing Track' % (t.cyl, t.head))
        usb.seek(t.physical_cyl, t.physical_head)
        for rev in range(args.revs):
            if args.hfreq:
                usb.write_track(flux_list = [ round(drive_ticks * 1.1) ],
                                cue_at_index = False,
                                terminate_at_index = False)
            else:
                usb.erase_track(drive_ticks * 1.1)


def main(argv) -> None:

    epilog = (util.drive_desc + "\n"
              + util.speed_desc + "\n" + util.tspec_desc)
    parser = util.ArgumentParser(usage='%(prog)s [options]',
                                 epilog=epilog)
    parser.add_argument("--device", help="device name (COM/serial port)")
    parser.add_argument("--drive", type=util.Drive(), default='A',
                        help="drive to read")
    parser.add_argument("--revs", type=util.min_int(1), metavar="N", default=1,
                        help="number of revolutions to erase per track")
    parser.add_argument("--tracks", type=util.TrackSet, metavar="TSPEC",
                        help="which tracks to erase")
    parser.add_argument("--hfreq", action="store_true",
                        help="erase by writing a high-frequency signal")
    parser.add_argument("--fake-index", type=util.period, metavar="SPEED",
                        help="fake index pulses at SPEED")
    parser.description = description
    parser.prog += ' ' + argv[1]
    args = parser.parse_args(argv[2:])

    try:
        usb = util.usb_open(args.device)
        tracks = util.TrackSet('c=0-81:h=0-1')
        if args.tracks is not None:
            tracks.update_from_trackspec(args.tracks.trackspec)
        args.tracks = tracks
        print(f'Erasing {args.tracks}, revs={args.revs}')
        util.with_drive_selected(lambda: erase(usb, args), usb, args.drive)
    except USB.CmdError as err:
        print("Command Failed: %s" % err)


if __name__ == "__main__":
    main(sys.argv)

# Local variables:
# python-indent: 4
# End:
