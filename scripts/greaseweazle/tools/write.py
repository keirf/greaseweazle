# greaseweazle/tools/write.py
#
# Greaseweazle control script: Write Image to Disk.
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

description = "Write a disk from the specified image file."

import sys

from greaseweazle.tools import util
from greaseweazle import error
from greaseweazle import usb as USB

# Read and parse the image file.
def open_image(args):
    cls = util.get_image_class(args.file)
    return cls.from_file(args.file)

class Formatter:
    def __init__(self):
        self.length = 0
    def print(self, s):
        self.erase()
        self.length = len(s)
        print(s, end="", flush=True)
    def erase(self):
        l = self.length
        print("\b"*l + " "*l + "\b"*l, end="", flush=True)
        self.length = 0

# write_from_image:
# Writes the specified image file to floppy disk.
def write_from_image(usb, args, image):

    # @drive_ticks is the time in Greaseweazle ticks between index pulses.
    # We will adjust the flux intervals per track to allow for this.
    drive_ticks = usb.read_track(2).ticks_per_rev

    verified_count, not_verified_count = 0, 0

    for t in args.tracks:

        cyl, head = t.cyl, t.head

        track = image.get_track(cyl, head)
        if track is None and not args.erase_empty:
            continue

        print("\r%sing Track %u.%u..." %
              ("Writ" if track is not None else "Eras", cyl, head),
              end="", flush=True)
        usb.seek(t.physical_cyl, head)
            
        if track is None:
            usb.erase_track(drive_ticks * 1.1)
            continue

        flux = track.flux_for_writeout()
            
        # @factor adjusts flux times for speed variations between the
        # read-in and write-out drives.
        factor = drive_ticks / flux.index_list[0]

        # Convert the flux samples to Greaseweazle sample frequency.
        rem = 0.0
        flux_list = []
        for x in flux.list:
            y = x * factor + rem
            val = round(y)
            rem = y - val
            flux_list.append(val)

        # Encode the flux times for Greaseweazle, and write them out.
        formatter = Formatter()
        verified = False
        for retry in range(3):
            usb.write_track(flux_list = flux_list,
                            cue_at_index = flux.index_cued,
                            terminate_at_index = flux.terminate_at_index)
            try:
                no_verify = args.no_verify or track.verify is None
            except AttributeError: # track.verify undefined
                no_verify = True
            if no_verify:
                not_verified_count += 1
                verified = True
                break
            v_revs = 1 if track.splice == 0 else 2
            v_flux = usb.read_track(v_revs)
            v_flux.cue_at_index()
            v_flux.scale(flux.time_per_rev / v_flux.time_per_rev)
            verified = track.verify.verify_track(v_flux)
            if verified:
                verified_count += 1
                break
            formatter.print(" Retry %d" % (retry + 1))
        formatter.erase()
        error.check(verified, "Failed to write Track %u.%u" % (cyl, head))

    print()
    if not_verified_count == 0:
        print("All tracks verified")
    else:
        if verified_count == 0:
            s = "No tracks verified "
        else:
            s = ("%d tracks verified; %d tracks *not* verified "
                 % (verified_count, not_verified_count))
        s += ("(Reason: Verify %s)"
              % ("unavailable", "disabled")[args.no_verify])
        print(s)


def main(argv):

    parser = util.ArgumentParser(usage='%(prog)s [options] file')
    parser.add_argument("--device", help="greaseweazle device name")
    parser.add_argument("--drive", type=util.drive_letter, default='A',
                        help="drive to write (A,B,0,1,2)")
    parser.add_argument("--tracks", type=util.TrackSet,
                        help="which tracks to write")
    parser.add_argument("--erase-empty", action="store_true",
                        help="erase empty tracks (default: skip)")
    parser.add_argument("--no-verify", action="store_true",
                        help="disable verify")
    parser.add_argument("file", help="input filename")
    parser.description = description
    parser.prog += ' ' + argv[1]
    args = parser.parse_args(argv[2:])

    try:
        usb = util.usb_open(args.device)
        image = open_image(args)
        tracks = util.TrackSet('c=0-81:h=0-1')
        if args.tracks is not None:
            tracks.update_from_trackspec(args.tracks.trackspec)
        args.tracks = tracks
        print("Writing %s" % (args.tracks))
        util.with_drive_selected(write_from_image, usb, args, image)
    except USB.CmdError as error:
        print("Command Failed: %s" % error)


if __name__ == "__main__":
    main(sys.argv)

# Local variables:
# python-indent: 4
# End:
