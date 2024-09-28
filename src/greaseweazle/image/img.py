# greaseweazle/image/img.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from typing import Dict, Tuple, Optional, Any

from greaseweazle import error
from greaseweazle.codec import codec
from greaseweazle.flux import HasFlux
from .image import Image, OptDict

class IMG(Image):

    sides_swapped = False
    sequential = False
    min_cyls: Optional[int] = None

    def __init__(self, name: str, fmt):
        self.to_track: Dict[Tuple[int,int],codec.Codec] = dict()
        error.check(fmt is not None, """\
Sector image requires a disk format to be specified""")
        self.filename = name
        self.fmt: codec.DiskDef = fmt


    def track_list(self):
        t, l = self.fmt.tracks, []
        if self.sequential:
            for h in t.heads:
                for c in t.cyls:
                    l.append((c,h))
        else:
            for c in t.cyls:
                for h in t.heads:
                    l.append((c,h))
        return l


    def from_bytes(self, dat: bytes) -> None:
        pos = 0
        for (cyl, head) in self.track_list():
            if self.sides_swapped:
                head ^= 1
            track = self.fmt.mk_track(cyl, head)
            if track is not None:
                pos += track.set_img_track(dat[pos:])
                self.to_track[cyl,head] = track


    def get_track(self, cyl: int, side: int) -> Optional[codec.Codec]:
        if (cyl,side) not in self.to_track:
            return None
        return self.to_track[cyl,side]


    def emit_track(self, cyl: int, side: int, track) -> None:
        self.to_track[cyl,side] = track


    def get_image(self) -> bytes:

        tdat = bytearray()

        # If min_cyls is specified, only emit extra cylinders if there is
        # valid data.
        max_cyl = None
        if self.min_cyls is not None:
            max_cyl = self.min_cyls - 1
            for (cyl, head) in self.track_list():
                if cyl > max_cyl and (cyl,head) in self.to_track:
                    track = self.to_track[cyl,head]
                    if track.nr_missing() < track.nsec:
                        max_cyl = cyl

        for (cyl, head) in self.track_list():
            if max_cyl is not None and cyl > max_cyl:
                break
            if self.sides_swapped:
                head ^= 1
            if (cyl,head) in self.to_track:
                t = self.to_track[cyl,head]
            else:
                _t = self.fmt.mk_track(cyl, head)
                assert _t is not None # mypy
                t = _t
            tdat += t.get_img_track()

        return tdat


class IMG_AutoFormat(IMG):

    @staticmethod
    def format_from_file(name: str) -> str:
        raise NotImplementedError

    @classmethod
    def from_file(cls, name: str, fmt: Optional[codec.DiskDef],
                  opts: OptDict) -> Image:
        if fmt is None:
            format_str = cls.format_from_file(name)
            fmt = codec.get_diskdef(format_str)
            print(f'{cls.__name__}: Image format {format_str}')
        return super().from_file(name, fmt, opts)

# Local variables:
# python-indent: 4
# End:
