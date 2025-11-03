# greaseweazle/tools/align.py
#
# Greaseweazle control script: Repeatedly read the same track for alignment.
#
# Released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

description = "Repeatedly read the same track for floppy drive alignment."

from typing import cast, Dict, Tuple, List, Type, Optional

import sys, copy, time

from greaseweazle.tools import util
from greaseweazle import error
from greaseweazle import usb as USB
from greaseweazle.flux import Flux, HasFlux
from greaseweazle.codec import codec
from greaseweazle.image import image

from greaseweazle import track
plls = track.plls

def read_and_normalise(usb: USB.Unit, args, revs: int, ticks=0) -> Flux:
    if args.fake_index is not None:
        drive_tpr = int(args.drive_ticks_per_rev)
        pre_index = int(usb.sample_freq * 0.5e-3)
        if ticks == 0:
            ticks = revs*drive_tpr + 2*pre_index
        flux = usb.read_track(revs=0, ticks=ticks)
        index_list = [pre_index] + [drive_tpr] * ((ticks-pre_index)//drive_tpr)
        flux.index_list = cast(List[float], index_list) # mypy
    else:
        flux = usb.read_track(revs=revs, ticks=ticks)
    flux._ticks_per_rev = args.drive_ticks_per_rev
    if args.reverse:
        flux.reverse()
    if args.hard_sectors and not args.raw:
        flux.identify_hard_sectors()
    if args.adjust_speed is not None:
        flux.scale(args.adjust_speed / flux.time_per_rev)
    return flux


def align_track(usb: USB.Unit, args) -> None:
    """Repeatedly reads the same track for alignment purposes.
    """

    args.ticks, args.drive_ticks_per_rev = 0, None

    if args.fake_index is not None:
        args.drive_ticks_per_rev = args.fake_index * usb.sample_freq
    elif args.hard_sectors:
        flux = usb.read_track(revs = 0, ticks = int(usb.sample_freq / 2))
        flux.identify_hard_sectors()
        assert flux.sector_list is not None # mypy
        args.drive_ticks_per_rev = flux.ticks_per_rev
        args.hard_sectors = len(flux.sector_list[-1])
        print(f'Drive reports {args.hard_sectors} hard sectors')
        del flux

    if isinstance(args.revs, float):
        if args.raw:
            args.revs = 2
        else:
            if args.drive_ticks_per_rev is None:
                args.drive_ticks_per_rev = usb.read_track(2).ticks_per_rev
            args.ticks = int(args.drive_ticks_per_rev * args.revs)
            args.revs = 2

    if args.hard_sectors:
        args.revs = (args.hard_sectors + 1) * (args.revs + 1)
        args.ticks = 0

    track_list = []
    for t in args.tracks:
        # Store track info as tuple since TrackIter reuses the same object
        track_list.append((t.cyl, t.head, t.physical_cyl, t.physical_head))
    
    if len(track_list) == 0:
        raise error.Fatal("Align command requires at least one track (e.g., c=40:h=0)")
    
    if len(track_list) > 1:
        cyl = track_list[0][0]  
        for track_info in track_list[1:]:
            if track_info[0] != cyl:
                raise error.Fatal("All tracks must be on the same cylinder for alignment")

    cyl = track_list[0][0]
    
    if len(track_list) == 1:
        _, head, physical_cyl, physical_head = track_list[0]
        tspec = f'T{cyl}.{head}'
        if physical_cyl != cyl or physical_head != head:
            tspec += f' <- Drive {physical_cyl}.{physical_head}'
        print(f"Aligning {tspec}, reading {args.reads} times, revs={args.revs}")
    else:
        heads = [str(track_info[1]) for track_info in track_list]  # head is index 1
        print(f"Aligning T{cyl} (alternating heads {','.join(heads)}), reading {args.reads} times, revs={args.revs}")
    
    if args.format:
        print("Format " + args.format)

    if args.gen_tg43:
        usb.set_pin(2, cyl < 60)

    for read_num in range(1, args.reads + 1):
        _, head, physical_cyl, physical_head = track_list[(read_num - 1) % len(track_list)]
        
        tspec = f'T{cyl}.{head}'
        if physical_cyl != cyl or physical_head != head:
            tspec += f' <- Drive {physical_cyl}.{physical_head}'
        
        usb.seek(physical_cyl, physical_head)
     
        flux = read_and_normalise(usb, args, args.revs, args.ticks)
        
        if args.fmt_cls is None:
            print(f'{tspec}: {flux.summary_string()}')
        else:
            dat = args.fmt_cls.decode_flux(cyl, head, flux)
            if dat is None:
                print("%s: WARNING: Out of range for format '%s': No format "
                      "conversion applied: %s" % (tspec, args.format,
                        flux.summary_string()))
            else:
                for pll in plls[1:]:
                    if dat.nr_missing() == 0:
                        break
                    dat.decode_flux(flux, pll)
                
                print("%s: %s from %s" % (tspec, dat.summary_string(),
                                            flux.summary_string()))
                
        if read_num < args.reads:
            time.sleep(0.1)


def main(argv) -> None:

    epilog = (util.drive_desc + "\n"
              + util.speed_desc + "\n" + util.tspec_desc
              + "\n" + util.pllspec_desc
              + "\nFORMAT options:\n" + codec.print_formats()
              + "\n\nNote: TRACKS can specify one track (e.g., c=40:h=0) or multiple heads on same cylinder (e.g., c=40:h=0,1) to alternate between heads")
    parser = util.ArgumentParser(usage='%(prog)s [options]',
                                 epilog=epilog)
    parser.add_argument("--device", help="device name (COM/serial port)")
    parser.add_argument("--drive", type=util.Drive(), default='A',
                        help="drive to read")
    parser.add_argument("--diskdefs", help="disk definitions file")
    parser.add_argument("--format", help="disk format for decoding")
    parser.add_argument("--revs", type=util.min_int(1), metavar="N", default=3,
                        help="number of revolutions to read per attempt")
    parser.add_argument("--tracks", type=util.TrackSet, metavar="TSPEC", required=True,
                        help="which track(s) to read (single track or multiple heads on same cylinder)")
    parser.add_argument("--reads", type=util.min_int(1), metavar="N", default=10,
                        help="number of times to read the track(s)")
    parser.add_argument("--raw", action="store_true",
                        help="read raw flux (no format decoding)")
    index_group = parser.add_mutually_exclusive_group(required=False)
    index_group.add_argument("--fake-index", type=util.period, metavar="SPEED",
                             help="fake index pulses at SPEED")
    index_group.add_argument("--hard-sectors", action="store_true",
                             help="read from a hard-sectored disk")
    parser.add_argument("--adjust-speed", type=util.period, metavar="SPEED",
                        help="scale track data to effective drive SPEED")
    parser.add_argument("--pll", type=track.PLL, metavar="PLLSPEC",
                        help="manual PLL parameter override")
    densel_group = parser.add_mutually_exclusive_group(required=False)
    densel_group.add_argument("--densel", "--dd", type=util.level, metavar="LEVEL",
                        help="drive interface density select on pin 2 (H,L)")
    densel_group.add_argument("--gen-tg43", action="store_true",
                        help="generate TG43 signal for 8-inch drive on pin 2 from track 60. Enable postcompensation filter")
    parser.add_argument("--reverse", action="store_true",
                        help="reverse track data (flippy disk)")
    parser.description = description
    parser.prog += ' ' + argv[1]
    args = parser.parse_args(argv[2:])

    if args.pll is not None:
        plls.insert(0, args.pll)

    try:
        usb = util.usb_open(args.device)
        def_tracks, args.fmt_cls = None, None
        if args.format:
            args.fmt_cls = codec.get_diskdef(args.format, args.diskdefs)
            if args.fmt_cls is None:
                raise error.Fatal("""\
Unknown format '%s'
Known formats:\n%s"""
                                  % (args.format, codec.print_formats(
                                      args.diskdefs)))
            def_tracks = copy.copy(args.fmt_cls.tracks)
            if args.revs is None: args.revs = args.fmt_cls.default_revs
        if def_tracks is None:
            def_tracks = util.TrackSet('c=0-81:h=0-1')
        if args.revs is None: args.revs = 3
        if args.tracks is not None:
            def_tracks.update_from_trackspec(args.tracks.trackspec)
        args.tracks = def_tracks

        try:
            if args.densel is not None or args.gen_tg43:
                prev_pin2 = usb.get_pin(2)
            if args.densel is not None:
                usb.set_pin(2, args.densel)
            util.with_drive_selected(
                lambda: align_track(usb, args), usb, args.drive)
        finally:
            if args.densel is not None or args.gen_tg43:
                usb.set_pin(2, prev_pin2)
    except USB.CmdError as err:
        print("Command Failed: %s" % err)


if __name__ == "__main__":
    main(sys.argv)

# Local variables:
# python-indent: 4
# End: