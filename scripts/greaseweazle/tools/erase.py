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

from greaseweazle.tools import util
from greaseweazle import usb as USB

def erase(usb, args):

    # @drive_ticks is the time in Greaseweazle ticks between index pulses.
    # We will adjust the flux intervals per track to allow for this.
    drive_ticks = usb.read_track(2).ticks_per_rev

    for t in args.tracks:
        cyl, head = t.cyl, t.head
        print("T%u.%u: Erasing Track" % (cyl, head))
        usb.seek(t.physical_cyl, t.physical_head)
        if args.hfreq:
            usb.write_track(flux_list = [ round(drive_ticks * 1.1) ],
                            cue_at_index = False,
                            terminate_at_index = False)
        else:
            usb.erase_track(drive_ticks * 1.1)


def main(argv):

    parser = util.ArgumentParser(usage='%(prog)s [options]')
    parser.add_argument("--device", help="device name (COM/serial port)")
    parser.add_argument("--drive", type=util.drive_letter, default='A',
                        help="drive to write (A,B,0,1,2)")
    parser.add_argument("--tracks", type=util.TrackSet, metavar="TSPEC",
                        help="which tracks to erase")
    parser.add_argument("--hfreq", action="store_true",
                        help="erase by writing a high-frequency signal")
    parser.description = description
    parser.prog += ' ' + argv[1]
    args = parser.parse_args(argv[2:])

    try:
        usb = util.usb_open(args.device)
        tracks = util.TrackSet('c=0-81:h=0-1')
        if args.tracks is not None:
            tracks.update_from_trackspec(args.tracks.trackspec)
        args.tracks = tracks
        print("Erasing %s" % (args.tracks))
        util.with_drive_selected(erase, usb, args)
    except USB.CmdError as error:
        print("Command Failed: %s" % error)


if __name__ == "__main__":
    main(sys.argv)

# Local variables:
# python-indent: 4
# End:
