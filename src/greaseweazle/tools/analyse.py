# greaseweazle/tools/analyse.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

description = "Analyse raw tracks to infer their format."

from typing import Type, List, Optional

import sys, copy

import greaseweazle.tools.read
from greaseweazle.tools import util
from greaseweazle import error
from greaseweazle.flux import Flux
from greaseweazle.codec import codec
from greaseweazle.image import image
from greaseweazle.track import plls, PLL, PLLTrack

from greaseweazle.codec.ibm import ibm
from greaseweazle.codec.amiga import amigados
from greaseweazle.codec.macintosh import mac_gcr
from greaseweazle.codec.commodore import c64_gcr

def open_input_image(args, image_class: Type[image.Image]) -> image.Image:
    return image_class.from_file(args.file, None)

def analyse_ibm(t: ibm.IBMTrack) -> Optional[str]:
    if isinstance(t, ibm.IBMTrack_Empty):
        return None
    if len(t.sectors) == 0:
        return None
    gaps2: List[int] = []
    gaps3: List[int] = []
    for i in range(len(t.sectors)):
        gap2 = t.sectors[i].dam.start - t.sectors[i].idam.end
        gap3 = t.sectors[i].start - t.sectors[i-1].end
        gap2 -= t.gap_presync*16
        gap3 -= t.gap_presync*16
        gaps2.append(gap2)
        gaps3.append(gap3)
    gap2 = sum(gaps2) / len(gaps2)
    s = f'  gap2: {round(gap2/16)}'
    if len(gaps3) > 1:
        gaps3 = gaps3[1:]
        gap3 = sum(gaps3) / len(gaps3)
        s += f'  gap3: {round(gap3/16)}'
    if len(t.iams) != 0:
        start = t.iams[0].start - t.gap_presync*16
        s += f'  gap4a: {round(start/16)}'
        start = t.sectors[0].start - t.gap_presync*16 - t.iams[0].start
        s += f'  gap1: {round(start/16)}'
    else:
        start = t.sectors[0].start - t.gap_presync*16
        s += f'  gap4a: {round(start/16)}'
    return s


def analyse(args, image: image.Image) -> None:

    defs = codec.get_all_diskdefs()
    
    ibm_def = defs['ibm.scan']
    amiga_dd_def = defs['amiga.amigados']
    amiga_hd_def = defs['amiga.amigados_hd']
    c64_dos_def = defs['commodore.1571']
    mac_def = defs['mac.800']

    for t in args.tracks:

        cyl, head = t.cyl, t.head

        track = image.get_track(t.physical_cyl, t.physical_head)
        if track is None:
            continue

        flux = track.flux()
        if args.adjust_speed is not None:
            flux.scale(args.adjust_speed / flux.time_per_rev)

        f = list()

        ibm_scan = ibm_def.mk_track(cyl, head)
        assert isinstance(ibm_scan, ibm.IBMTrack_Scan)
        ibm_scan.decode_flux(flux)
        ibm_analysis = analyse_ibm(ibm_scan.track)
        if ibm_scan.track.nsec:
            f.append(str(ibm_scan.track.mode))

        amiga_dd = amiga_dd_def.mk_track(cyl, head)
        assert isinstance(amiga_dd, amigados.AmigaDOS_DD)
        amiga_dd.decode_flux(flux)
        if amiga_dd.nsec != amiga_dd.nr_missing():
            f.append('AmigaDOS DD')

        amiga_hd = amiga_hd_def.mk_track(cyl, head)
        assert isinstance(amiga_hd, amigados.AmigaDOS_HD)
        amiga_hd.decode_flux(flux)
        if amiga_hd.nsec != amiga_hd.nr_missing():
            f.append('AmigaDOS HD')

        c64_dos = c64_dos_def.mk_track(cyl, head)
        assert isinstance(c64_dos, c64_gcr.C64GCR)
        c64_dos.decode_flux(flux)
        if c64_dos.nsec != c64_dos.nr_missing():
            f.append('C64 GCR')

        mac = mac_def.mk_track(cyl, head)
        assert isinstance(mac, mac_gcr.MacGCR)
        mac.decode_flux(flux)
        if mac.nsec != mac.nr_missing():
            f.append('Mac GCR')

        s = ''
        if f:
            s += f'T{cyl}.{head}: {", ".join(f)}'
        if ibm_analysis:
            s += ibm_analysis
        if s:
            print(s)


def main(argv) -> None:

    epilog = (util.speed_desc + "\n" + util.tspec_desc
              + "\n" + util.pllspec_desc)
    parser = util.ArgumentParser(usage='%(prog)s [options] file',
                                 epilog=epilog)
    parser.add_argument("--tracks", type=util.TrackSet,
                        help="which tracks to read & analyse from input",
                        metavar="TSPEC")
    parser.add_argument("--adjust-speed", type=util.period, metavar="SPEED",
                        help="scale track data to effective drive SPEED")
    parser.add_argument("--pll", type=PLL, metavar="PLLSPEC",
                        help="manual PLL parameter override")
    parser.add_argument("file", help="input filename")
    parser.description = description
    parser.prog += ' ' + argv[1]
    args = parser.parse_args(argv[2:])

    if args.pll is not None:
        plls.insert(0, args.pll)

    image_class = util.get_image_class(args.file)

    def_tracks = util.TrackSet('c=0-9:h=0-1')
    if args.tracks is not None:
        def_tracks.update_from_trackspec(args.tracks.trackspec)
    args.tracks = def_tracks

    print("Analysing %s " % args.tracks)

    image = open_input_image(args, image_class)
    analyse(args, image)


# Local variables:
# python-indent: 4
# End:
