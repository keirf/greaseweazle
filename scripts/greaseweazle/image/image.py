# greaseweazle/image/image.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import os

from greaseweazle import error
import greaseweazle.codec.amiga.amigados as amigados

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
    def to_file(cls, name, start_cyl, nr_sides):
        error.check(not cls.read_only,
                    "%s: Cannot create %s image files" % (name, cls.__name__))
        obj = cls(start_cyl, nr_sides)
        obj.filename = name
        return obj


# Local variables:
# python-indent: 4
# End:
