# greaseweazle/image/image.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from __future__ import annotations
from typing import Optional, List

import os

from greaseweazle import error
from greaseweazle.codec import codec
from greaseweazle.flux import HasFlux

class ImageOpts:
    r_settings: List[str] = [] # r_set()
    w_settings: List[str] = [] # w_set()
    a_settings: List[str] = [] # r_set(), w_set()

    def _set(self, filename: str, opt: str, val: str,
             settings: List[str]) -> None:
        error.check(opt in settings,
                    "%s: Invalid file option: %s\n" % (filename, opt)
                    + 'Valid options: '
                    + (', '.join(settings) if settings else '<none>'))
        setattr(self, opt, val)

    def r_set(self, filename: str, opt: str, val: str) -> None:
        self._set(filename, opt, val, self.a_settings + self.r_settings)

    def w_set(self, filename: str, opt: str, val: str) -> None:
        self._set(filename, opt, val, self.a_settings + self.w_settings)

class Image:

    default_format: Optional[str] = None
    read_only = False
    write_on_ctrl_c = False
    opts = ImageOpts() # empty

    ## Context manager for image objects created using .to_file()

    def __enter__(self):
        self.file = open(self.filename, ('wb','xb')[self.noclobber])
        return self

    def __exit__(self, type, value, tb):
        save = (type is None or
                (type is KeyboardInterrupt and self.write_on_ctrl_c))
        try:
            if save:
                # No error: Normal writeout.
                self.file.write(self.get_image())
        finally:
            # Always close the file.
            self.file.close()
        if not save:
            # An error occurred: We remove the target file.
            os.remove(self.filename)

    ## Default .to_file() constructor
    @classmethod
    def to_file(cls, name, fmt, noclobber):
        error.check(not cls.read_only,
                    "%s: Cannot create %s image files" % (name, cls.__name__))
        obj = cls()
        obj.filename = name
        obj.fmt = fmt
        obj.noclobber = noclobber
        return obj

    # Maximum non-empty cylinder on each head, or -1 if no cylinders exist.
    # Returns a list of integers, indexed by head.
    def max_cylinder(self):
        r = list()
        for h in range(2):
            for c in range(100, -2, -1):
                if c < 0 or self.get_track(c,h) is not None:
                    r.append(c)
                    break
        return r

    ## Above methods and class variables can be overridden by subclasses.
    ## Additionally, subclasses must provide following public interfaces:

    ## Read support:
    @classmethod
    def from_file(cls, name: str, fmt: Optional[codec.DiskDef]) -> Image:
        raise NotImplementedError

    def get_track(self, cyl: int, side: int) -> Optional[HasFlux]:
        raise NotImplementedError

    ## Write support (if not cls.read_only):
    def emit_track(self, cyl: int, side: int, track: HasFlux):
        raise NotImplementedError
    ## Plus get_image, or __enter__ / __exit__
    def get_image(self) -> bytes:
        raise NotImplementedError


# Local variables:
# python-indent: 4
# End:
