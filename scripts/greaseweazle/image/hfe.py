# greaseweazle/image/hfe.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

class HFE:

    def __init__(self, start_cyl, nr_sides):
        self.start_cyl = start_cyl
        self.nr_sides = nr_sides
        self.nr_revs = None
        self.track_list = []


    @classmethod
    def from_file(cls, dat):
        hfe = cls(0, 2)
        return hfe


    def get_track(self, cyl, side, writeout=False):
        return None
    
        
    def append_track(self, flux):
        pass


    def get_image(self):
        return bytes()


# Local variables:
# python-indent: 4
# End:
