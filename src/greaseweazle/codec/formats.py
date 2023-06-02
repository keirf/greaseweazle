# greaseweazle/codec/formats.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import os.path, re
import importlib.resources
from copy import copy

from greaseweazle import error
from greaseweazle.codec import bitcell
from greaseweazle.codec.ibm import ibm
from greaseweazle.codec.amiga import amigados
from greaseweazle.codec.macintosh import mac_gcr
from greaseweazle.codec.commodore import c64_gcr
from greaseweazle.tools import util

class Disk_Config:

    def __init__(self):
        self.cyls, self.heads = None, None
        self.step = 1
        self.track_map = dict()

    def add_param(self, key, val):
        if key == 'cyls':
            val = int(val)
            error.check(1 <= val <= 255, '%s out of range' % key)
            self.cyls = val
        elif key == 'heads':
            val = int(val)
            error.check(1 <= val <= 2, '%s out of range' % key)
            self.heads = val
        elif key == 'step':
            val = int(val)
            error.check(1 <= val <= 4, '%s out of range' % key)
            self.step = val
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

    def mk_track(self, cyl, head):
        if (cyl, head) not in self.track_map:
            return None
        return self.track_map[cyl, head].mk_track(cyl, head)
    
    def decode_track(self, cyl, head, track):
        t = self.mk_track(cyl, head)
        if t is not None:
            t.decode_raw(track)
        return t

    @property
    def default_revs(self):
        return max([x.default_revs for x in self.track_map.values()])


class ParseMode:
    Outer = 0
    Disk  = 1
    Track = 2


def get_cfg_lines(cfg):
    if cfg is None:
        cfg = 'diskdefs.cfg'
        with importlib.resources.open_text('greaseweazle.data', cfg) as f:
            lines = f.readlines()
    else:
        with open(os.path.expanduser(cfg), 'r') as f:
            lines = f.readlines()
    return (lines, cfg)


def mk_track_config(format_name):
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


def get_format(name, cfg=None):
    parse_mode = ParseMode.Outer
    active, formats = False, []
    disk, track = None, None
    lines, cfg = get_cfg_lines(cfg)

    for linenr, l in enumerate(lines, start=1):
        try:
            # Strip comments and whitespace.
            t = re.match(r'\s*([^#]*)', l).group(1).strip()

            # Skip empty lines.
            if not t:
                continue

            if parse_mode == ParseMode.Outer:
                disk_match = re.match(r'disk\s+([\w,.-]+)', t)
                error.check(disk_match is not None,
                            'syntax error')
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
                    error.check(disk.cyls is not None,
                                'missing cyls')
                    error.check(disk.heads is not None,
                                'missing heads')
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

                keyval_match = re.match(r'([a-zA-Z0-9:,._-]+)\s*='
                                        '\s*([a-zA-Z0-9:,._-]+)', t)
                error.check(keyval_match is not None, 'syntax error')
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

                keyval_match = re.match(r'([a-zA-Z0-9:,._-]+)\s*='
                                        '\s*([a-zA-Z0-9:,._*-]+)', t)
                error.check(keyval_match is not None, 'syntax error')
                track.add_param(keyval_match.group(1),
                                keyval_match.group(2))

        except Exception as err:
            s = "%s, line %d: " % (cfg, linenr)
            err.args = (s + err.args[0],) + err.args[1:]
            raise

    if disk is None:
        return None
    disk.finalise()

    return disk


def print_formats(cfg=None):
    columns, sep, formats = 80, 2, []
    lines, _ = get_cfg_lines(cfg)
    for l in lines:
        disk_match = re.match(r'\s*disk\s+([\w,.-]+)', l)
        if disk_match:
            formats.append(disk_match.group(1))
    formats.sort()
    return util.columnify(formats)
