# greaseweazle/image/image.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import os

from greaseweazle import error

class Image:

    read_only = False

    ## Context manager for image objects created using .to_file()

    def __enter__(self):
        self.file = open(self.filename, "wb")
        return self

    def __exit__(self, type, value, tb):
        try:
            if type is None:
                # No error: Normal writeout.
                self.file.write(self.get_image())
        finally:
            # Always close the file.
            self.file.close()
        if type is not None:
            # An error occurred: We remove the target file.
            os.remove(self.filename)

    ## Default .to_file() constructor
    @classmethod
    def to_file(cls, name, fmt=None):
        error.check(not cls.read_only,
                    "%s: Cannot create %s image files" % (name, cls.__name__))
        obj = cls()
        obj.filename = name
        obj.fmt = fmt
        return obj

    ## Above methods and class variables can be overridden by subclasses.
    ## Additionally, subclasses must provide following public interfaces:

    ## Read support:
    # def from_file(cls, name)
    # def get_track(self, cyl, side)

    ## Write support (if not cls.read_only):
    # def emit_track(self, cyl, side, track)
    ## Plus either:
    # def get_image(self)
    ## Or:
    # __enter__ / __exit__


# Local variables:
# python-indent: 4
# End:
