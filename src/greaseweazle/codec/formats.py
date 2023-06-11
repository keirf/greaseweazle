# greaseweazle/codec/formats.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from typing import Dict, List, Tuple, Optional

import os.path, re
import importlib.resources
from copy import copy
from abc import abstractmethod

from greaseweazle import error
from greaseweazle.codec import codec
from greaseweazle.tools import util

class Track_Config:

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
    

class Disk_Config:

    def __init__(self) -> None:
        self.cyls: Optional[int] = None
        self.heads: Optional[int] = None
        self.step = 1
        self.track_map: Dict[Tuple[int,int],Track_Config] = dict()

    def add_param(self, key: str, val: str) -> None:
        if key == 'cyls':
            n = int(val)
            error.check(1 <= n <= 255, '%s out of range' % key)
            self.cyls = n
        elif key == 'heads':
            n = int(val)
            error.check(1 <= n <= 2, '%s out of range' % key)
            self.heads = n
        elif key == 'step':
            n = int(val)
            error.check(1 <= n <= 4, '%s out of range' % key)
            self.step = n
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
        if self.step > 1:
            s += ':step=' + str(self.step)
        return s

    def mk_track(self, cyl: int, head: int) -> Optional[codec.Codec]:
        if (cyl, head) not in self.track_map:
            return None
        return self.track_map[cyl, head].mk_track(cyl, head)
    
    def decode_track(self, cyl: int, head: int, track) -> Optional[codec.Codec]:
        t = self.mk_track(cyl, head)
        if t is not None:
            t.decode_raw(track)
        return t

    @property
    def default_revs(self) -> float:
        return max([x.default_revs for x in self.track_map.values()])


class ParseMode:
    Outer = 0
    Disk  = 1
    Track = 2


def get_cfg_lines(cfg: Optional[str]) -> Tuple[List[str], str]:
    if cfg is None:
        cfg = 'diskdefs.cfg'
        with importlib.resources.open_text('greaseweazle.data', cfg) as f:
            lines = f.readlines()
    else:
        with open(os.path.expanduser(cfg), 'r') as f:
            lines = f.readlines()
    return (lines, cfg)

# Import the Track_Config subclasses
from greaseweazle.codec import bitcell
from greaseweazle.codec.ibm import ibm
from greaseweazle.codec.amiga import amigados
from greaseweazle.codec.macintosh import mac_gcr
from greaseweazle.codec.commodore import c64_gcr

def mk_track_config(format_name: str) -> Track_Config:
    if format_name in ['amiga.amigados']:
        return amigados.AmigaDOS_Config(format_name)
    if format_name in ['ibm.mfm', 'ibm.fm', 'dec.rx02']:
        return ibm.IBMTrack_Fixed_Config(format_name)
    if format_name in ['ibm.scan']:
        return ibm.IBMTrack_Scan_Config(format_name)
    if format_name in ['mac.gcr']:
        return mac_gcr.MacGCR_Config(format_name)
    if format_name in ['c64.gcr']:
        return c64_gcr.C64GCR_Config(format_name)
    if format_name in ['bitcell']:
        return bitcell.BitcellTrack_Config(format_name)
    raise error.Fatal('unrecognised format name: %s' % format_name)

def get_format(name, cfg: Optional[str] = None) -> Optional[Disk_Config]:
    parse_mode = ParseMode.Outer
    active = False
    disk: Optional[Disk_Config] = None
    track: Optional[Track_Config] = None
    lines, cfg = get_cfg_lines(cfg)

    for linenr, l in enumerate(lines, start=1):
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
                error.check(disk_match is not None, 'syntax error')
                assert disk_match is not None # mypy
                parse_mode = ParseMode.Disk
                active = disk_match.group(1) == name
                if active:
                    disk = Disk_Config()

            elif parse_mode == ParseMode.Disk:
                if t == 'end':
                    parse_mode = ParseMode.Outer
                    active = False
                    continue
                tracks_match = re.match(r'tracks\s+([0-9,.*-]+)'
                                        '\s+([\w,.-]+)', t)
                if tracks_match:
                    parse_mode = ParseMode.Track
                    if not active:
                        continue
                    assert disk is not None # mypy
                    error.check(disk.cyls is not None, 'missing cyls')
                    error.check(disk.heads is not None, 'missing heads')
                    assert disk.cyls is not None # mypy
                    assert disk.heads is not None # mypy
                    track = mk_track_config(tracks_match.group(2))
                    for x in tracks_match.group(1).split(','):
                        if x == '*':
                            for c in range(disk.cyls):
                                for hd in range(disk.heads):
                                    if (c,hd) not in disk.track_map:
                                        disk.track_map[c,hd] = track
                        else:
                            t_match = re.match(r'(\d+)(?:-(\d+))?'
                                               '(?:\.([01]))?', x)
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
                                        '\s*([a-zA-Z0-9:,._-]+)', t)
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
                                        '\s*([a-zA-Z0-9:,._*-]+)', t)
                error.check(keyval_match is not None, 'syntax error')
                assert keyval_match is not None # mypy
                track.add_param(keyval_match.group(1),
                                keyval_match.group(2))

        except Exception as err:
            ctxt = "%s, line %d: " % (cfg, linenr)
            err.args = (ctxt + err.args[0],) + err.args[1:]
            raise

    if disk is None:
        return None
    disk.finalise()

    return disk


def print_formats(cfg: Optional[str] = None) -> str:
    columns, sep, formats = 80, 2, []
    lines, _ = get_cfg_lines(cfg)
    for l in lines:
        disk_match = re.match(r'\s*disk\s+([\w,.-]+)', l)
        if disk_match:
            formats.append(disk_match.group(1))
    formats.sort()
    return util.columnify(formats)
