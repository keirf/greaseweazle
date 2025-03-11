# greaseweazle/codec/codec.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from __future__ import annotations
from typing import Dict, List, Tuple, Optional

import os.path, re
import importlib.resources
from copy import copy
from abc import abstractmethod

from greaseweazle import error
from greaseweazle.codec import codec
from greaseweazle.tools import util
from greaseweazle.track import MasterTrack, PLL
from greaseweazle.flux import Flux, HasFlux, WriteoutFlux


class Codec:

    @property
    @abstractmethod
    def nsec(self) -> int:
        ...

    @abstractmethod
    def summary_string(self) -> str:
        ...

    @abstractmethod
    def has_sec(self, sec_id: int) -> bool:
        ...

    @abstractmethod
    def nr_missing(self) -> int:
        ...

    @abstractmethod
    def get_img_track(self) -> bytearray:
        ...

    @abstractmethod
    def set_img_track(self, tdat: bytes) -> int:
        ...

    @abstractmethod
    def decode_flux(self, track: HasFlux, pll: Optional[PLL] = None) -> None:
        ...

    @abstractmethod
    def master_track(self) -> MasterTrack:
        ...

    def flux(self) -> Flux:
        return self.master_track().flux()

    def flux_for_writeout(self, cue_at_index) -> WriteoutFlux:
        return self.master_track().flux_for_writeout(cue_at_index)


class TrackDef:

    default_revs: float

    @abstractmethod
    def add_param(self, key: str, val) -> None:
        ...

    @abstractmethod
    def finalise(self) -> None:
        ...

    @abstractmethod
    def mk_track(self, cyl: int, head: int) -> codec.Codec:
        ...
    

class DiskDef:

    def __init__(self) -> None:
        self.cyls: Optional[int] = None
        self.heads: Optional[int] = None
        self.track_map: Dict[Tuple[int,int],TrackDef] = dict()

    def add_param(self, key: str, val: str) -> None:
        if key == 'cyls':
            n = int(val)
            error.check(1 <= n <= 255, '%s out of range' % key)
            self.cyls = n
        elif key == 'heads':
            n = int(val)
            error.check(1 <= n <= 2, '%s out of range' % key)
            self.heads = n
        else:
            raise error.Fatal('unrecognised disk option: %s' % key)

    def finalise(self):
        error.check(self.cyls is not None, 'missing cyls')
        error.check(self.heads is not None, 'missing heads')
        self.tracks = util.TrackSet(self.trackset())

    def trackset(self):
        s = 'c=0'
        if self.cyls > 1:
            s += '-' + str(self.cyls-1)
        s += ':h=0'
        if self.heads > 1:
            s += '-' + str(self.heads-1)
        return s

    def mk_track(self, cyl: int, head: int) -> Optional[codec.Codec]:
        if (cyl, head) not in self.track_map:
            return None
        return self.track_map[cyl, head].mk_track(cyl, head)
    
    def decode_flux(self, cyl: int, head: int,
                    track: HasFlux) -> Optional[codec.Codec]:
        t = self.mk_track(cyl, head)
        if t is not None:
            t.decode_flux(track)
        return t

    @property
    def default_revs(self) -> float:
        return max([x.default_revs for x in self.track_map.values()])


class DiskDef_File:
    def __init__(self, name: Optional[str],
                 parent: Optional[DiskDef_File] = None) -> None:
        self.path: Optional[str] = None
        self.name: str = 'diskdefs.cfg' if name is None else name
        if name is None or (parent and not parent.path):
            with importlib.resources.open_text('greaseweazle.data',
                                               self.name) as f:
                self.lines = f.readlines()
        else:
            if parent:
                assert parent.path # mypy
                self.path = os.path.join(os.path.dirname(parent.path),
                                         self.name)
            else:
                self.path = os.path.expanduser(self.name)
            with open(self.path, 'r') as f:
                self.lines = f.readlines()


# Import the TrackDef subclasses
from greaseweazle.codec import bitcell
from greaseweazle.codec.ibm import ibm
from greaseweazle.codec.amiga import amigados
from greaseweazle.codec.macintosh import mac_gcr
from greaseweazle.codec.commodore import c64_gcr
from greaseweazle.codec.apple2 import apple2_gcr
from greaseweazle.codec.hp import hp_mmfm
from greaseweazle.codec.northstar import northstar
from greaseweazle.codec.micropolis import micropolis
from greaseweazle.codec.datageneral import datageneral

def mk_trackdef(format_name: str) -> TrackDef:
    if format_name in ['amiga.amigados']:
        return amigados.AmigaDOSDef(format_name)
    if format_name in ['ibm.mfm', 'ibm.fm', 'dec.rx02']:
        return ibm.IBMTrack_FixedDef(format_name)
    if format_name in ['ibm.scan']:
        return ibm.IBMTrack_ScanDef(format_name)
    if format_name in ['mac.gcr']:
        return mac_gcr.MacGCRDef(format_name)
    if format_name in ['c64.gcr']:
        return c64_gcr.C64GCRDef(format_name)
    if format_name in ['hp.mmfm']:
        return hp_mmfm.HPMMFMDef(format_name)
    if format_name in ['northstar']:
        return northstar.NorthStarDef(format_name)
    if format_name in ['micropolis']:
        return micropolis.MicropolisDef(format_name)
    if format_name in ['apple2.gcr']:
        return apple2_gcr.Apple2GCRDef(format_name)
    if format_name in ['bitcell']:
        return bitcell.BitcellTrackDef(format_name)
    if format_name in ['datageneral']:
        return datageneral.DataGeneralDef(format_name)
    raise error.Fatal('unrecognised format name: %s' % format_name)


class ParseMode:
    Outer = 0
    Disk  = 1
    Track = 2

def _get_diskdef(
        format_name: str,
        prefix: str,
        diskdef_file: DiskDef_File
) -> Optional[DiskDef]:

    parse_mode = ParseMode.Outer
    active = False
    disk: Optional[DiskDef] = None
    track: Optional[TrackDef] = None

    for linenr, l in enumerate(diskdef_file.lines, start=1):
        try:
            # Strip comments and whitespace.
            match = re.match(r'\s*([^#]*)', l)
            assert match is not None # mypy
            t = match.group(1).strip()

            # Skip empty lines.
            if not t:
                continue

            if parse_mode == ParseMode.Outer:
                disk_match = re.match(r'disk\s+([\w,.-]+)', t)
                if disk_match:
                    parse_mode = ParseMode.Disk
                    active = ((prefix + disk_match.group(1).casefold())
                              == format_name)
                    if active:
                        disk = DiskDef()
                else:
                    import_match = re.match(r'import\s+([\w,.-]*)\s*"([^"]+)"',
                                            t)
                    error.check(import_match is not None, 'syntax error')
                    assert import_match is not None # mypy
                    sub_prefix = prefix + import_match.group(1).casefold()
                    if format_name.startswith(sub_prefix):
                        disk = _get_diskdef(format_name, sub_prefix,
                                            DiskDef_File(
                                                name = import_match.group(2),
                                                parent = diskdef_file))
                        if disk:
                            break

            elif parse_mode == ParseMode.Disk:
                if t == 'end':
                    parse_mode = ParseMode.Outer
                    active = False
                    if disk:
                        break
                    continue
                tracks_match = re.match(r'tracks\s+([0-9,.*-]+)'
                                        r'\s+([\w,.-]+)', t)
                if tracks_match:
                    parse_mode = ParseMode.Track
                    if not active:
                        continue
                    assert disk is not None # mypy
                    error.check(disk.cyls is not None, 'missing cyls')
                    error.check(disk.heads is not None, 'missing heads')
                    assert disk.cyls is not None # mypy
                    assert disk.heads is not None # mypy
                    track = mk_trackdef(tracks_match.group(2))
                    for x in tracks_match.group(1).split(','):
                        if x == '*':
                            for c in range(disk.cyls):
                                for hd in range(disk.heads):
                                    if (c,hd) not in disk.track_map:
                                        disk.track_map[c,hd] = track
                        else:
                            t_match = re.match(r'(\d+)(?:-(\d+))?'
                                               r'(?:\.([01]))?', x)
                            error.check(t_match is not None,
                                        'bad track specifier')
                            assert t_match is not None # mypy
                            s = int(t_match.group(1))
                            e = t_match.group(2)
                            e = s if e is None else int(e)
                            h = t_match.group(3)
                            if h is None:
                                h = list(range(disk.heads))
                            else:
                                error.check(int(h) < disk.heads,
                                            'head out of range')
                                h = [int(h)]
                            error.check(0 <= s < disk.cyls
                                        and 0 <= e < disk.cyls
                                        and s <= e,
                                        'cylinder out of range')
                            for c in range(s,e+1):
                                for hd in h:
                                    disk.track_map[c,hd] = track
                    continue

                if not active:
                    continue
                assert disk is not None # mypy

                keyval_match = re.match(r'([a-zA-Z0-9:,._-]+)\s*='
                                        r'\s*([a-zA-Z0-9:,._-]+)', t)
                error.check(keyval_match is not None, 'syntax error')
                assert keyval_match is not None # mypy
                disk.add_param(keyval_match.group(1),
                               keyval_match.group(2))

            elif parse_mode == ParseMode.Track:
                if t == 'end':
                    parse_mode = ParseMode.Disk
                    if track is not None:
                        track.finalise()
                        track = None
                    continue

                if not active:
                    continue
                assert track is not None # mypy

                keyval_match = re.match(r'([a-zA-Z0-9:,._-]+)\s*='
                                        r'\s*([a-zA-Z0-9:,._*-]+)', t)
                error.check(keyval_match is not None, 'syntax error')
                assert keyval_match is not None # mypy
                track.add_param(keyval_match.group(1),
                                keyval_match.group(2))

        except Exception as err:
            if err.args and isinstance(x := err.args[0], str):
                ctxt = f'At {diskdef_file.name}, line {linenr}:'
                ctxt += '\n' if x.startswith('At') else ' '
                err.args = (ctxt + x,) + err.args[1:]
            raise

    return disk

def get_diskdef(
        format_name: str,
        diskdef_filename: Optional[str] = None
) -> Optional[DiskDef]:
    diskdef_file = DiskDef_File(name = diskdef_filename)
    disk = _get_diskdef(format_name.casefold(), '', diskdef_file)
    if disk is None:
        return None
    disk.finalise()
    return disk

def get_all_formats(prefix: str, diskdef_file: DiskDef_File) -> List[str]:
    formats = []
    for l in diskdef_file.lines:
        disk_match = re.match(r'\s*disk\s+([\w,.-]+)', l)
        if disk_match:
            formats.append(prefix + disk_match.group(1))
        import_match = re.match(r'\s*import\s+([\w,.-]*)\s*"([^"]+)"', l)
        if import_match:
            formats += get_all_formats(
                prefix + import_match.group(1),
                DiskDef_File(
                    name = import_match.group(2),
                    parent = diskdef_file))
    return formats

def print_formats(diskdef_filename: Optional[str] = None) -> str:
    formats = get_all_formats('', DiskDef_File(name = diskdef_filename))
    formats.sort()
    return util.columnify(formats)

# Local variables:
# python-indent: 4
# End:
