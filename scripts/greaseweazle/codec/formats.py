
from greaseweazle.tools import util

class Format:
    img_compatible = False
    default_trackset = 'c=0-79:h=0-1'
    def __init__(self):
        self.tracks = util.TrackSet(self.default_trackset)

class Format_Amiga_AmigaDOS(Format):
    def __init__(self):
        import greaseweazle.codec.amiga.amigados as m
        self.fmt = m.AmigaDOS
        self.default_revs = m.default_revs
        self.decode_track = m.decode_track
        super().__init__()
    
class Format_IBM_720(Format):
    img_compatible = True
    def __init__(self):
        import greaseweazle.codec.ibm.mfm as m
        self.fmt = m.IBM_MFM_720
        self.default_revs = m.default_revs
        self.decode_track = self.fmt.decode_track
        super().__init__()
    
class Format_IBM_1440(Format):
    img_compatible = True
    def __init__(self):
        import greaseweazle.codec.ibm.mfm as m
        self.fmt = m.IBM_MFM_1M44
        self.default_revs = m.default_revs
        self.decode_track = self.fmt.decode_track
        super().__init__()

    
formats = {
    'amiga.amigados': Format_Amiga_AmigaDOS,
    'ibm.720': Format_IBM_720,
    'ibm.1440': Format_IBM_1440
}

def print_formats(f = None):
    s = ''
    for k, v in sorted(formats.items()):
        if not f or f(k, v):
            s += k if not s else ', ' + k
    return s
