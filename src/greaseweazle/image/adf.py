# greaseweazle/image/adf.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from greaseweazle import error
import greaseweazle.codec.amiga.amigados as amigados
from .img import IMG
from .image import Image

from greaseweazle.codec import formats

class ADF(Image):

    default_format = 'amiga.amigados'

    def __init__(self, name, fmt):
        self.to_track = dict()
        error.check(fmt is not None and fmt.adf_compatible, """\
ADF image requires compatible format conversion""")
        self.filename = name
        self.fmt = fmt


    @classmethod
    def from_file(cls, name, fmt):

        if fmt is not None and fmt.img_compatible: # Acorn ADF
            return IMG.from_file(name, fmt)

        with open(name, "rb") as f:
            dat = f.read()

        adf = cls(name, fmt)

        pos = 0
        for t in fmt.tracks:
            tnr = t.cyl*2 + t.head
            ados = fmt.fmt(t.cyl, t.head)
            if ados is not None:
                pos += ados.set_adf_track(dat[pos:])
                adf.to_track[tnr] = ados

        error.check(pos >= len(dat),
                    'Unexpected extra data at end of ADF image: '
                    'try --format=amiga.amigados_hd')

        return adf


    @classmethod
    def to_file(cls, name, fmt, noclobber):
        if fmt is not None and fmt.img_compatible: # Acorn ADF
            return IMG.to_file(name, fmt, noclobber)
        adf = cls(name, fmt)
        adf.noclobber = noclobber
        return adf


    def get_track(self, cyl, side):
        tnr = cyl * 2 + side
        if not tnr in self.to_track:
            return None
        return self.to_track[tnr].raw_track()


    def emit_track(self, cyl, side, track):
        tnr = cyl * 2 + side
        self.to_track[tnr] = track


    def get_image(self):

        tdat = bytearray()

        ntracks = max(self.to_track, default=0) + 1
        nsec = self.fmt.fmt(0,0).nsec

        for tnr in range(ntracks):
            t = self.to_track[tnr] if tnr in self.to_track else None
            if t is not None and hasattr(t, 'get_adf_track'):
                tdat += t.get_adf_track()
            elif tnr < 160:
                # Pad empty/damaged tracks.
                tdat += amigados.bad_sector * nsec
            else:
                # Do not extend past 160 tracks unless there is data.
                break

        if ntracks < 160:
            tdat += amigados.bad_sector * nsec * (160 - ntracks)

        return tdat


# Local variables:
# python-indent: 4
# End:
