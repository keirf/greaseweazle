# greaseweazle/codec/formats.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from collections import OrderedDict

from greaseweazle.tools import util

class Format:
    adf_compatible = False
    img_compatible = False
    default_trackset = 'c=0-79:h=0-1'
    max_trackset = 'c=0-81:h=0-1'
    def __init__(self):
        self.default_tracks = util.TrackSet(self.default_trackset)
        self.max_tracks = util.TrackSet(self.max_trackset)
        self.decode_track = self.fmt.decode_track

class Format_Acorn_DFS_SS(Format):
    img_compatible = True
    default_trackset = 'c=0-39:h=0'
    max_trackset = 'c=0-81:h=0'
    def __init__(self):
        import greaseweazle.codec.ibm.fm as m
        self.fmt = m.Acorn_DFS
        self.default_revs = m.default_revs
        super().__init__()
    
class Format_Acorn_DFS_DS(Format):
    img_compatible = True
    default_trackset = 'c=0-39:h=0-1'
    max_trackset = 'c=0-81:h=0-1'
    def __init__(self):
        import greaseweazle.codec.ibm.fm as m
        self.fmt = m.Acorn_DFS
        self.default_revs = m.default_revs
        super().__init__()

class Format_Acorn_ADFS_160(Format):
    img_compatible = True
    default_trackset = 'c=0-39:h=0'
    max_trackset = 'c=0-81:h=0'
    def __init__(self):
        import greaseweazle.codec.ibm.mfm as m
        self.fmt = m.Acorn_ADFS_640
        self.default_revs = m.default_revs
        super().__init__()
    
class Format_Acorn_ADFS_320(Format):
    img_compatible = True
    default_trackset = 'c=0-79:h=0'
    max_trackset = 'c=0-81:h=0'
    def __init__(self):
        import greaseweazle.codec.ibm.mfm as m
        self.fmt = m.Acorn_ADFS_640
        self.default_revs = m.default_revs
        super().__init__()

class Format_Acorn_ADFS_640(Format):
    img_compatible = True
    def __init__(self):
        import greaseweazle.codec.ibm.mfm as m
        self.fmt = m.Acorn_ADFS_640
        self.default_revs = m.default_revs
        super().__init__()
    
class Format_Acorn_ADFS_800(Format):
    img_compatible = True
    def __init__(self):
        import greaseweazle.codec.ibm.mfm as m
        self.fmt = m.Acorn_ADFS_800
        self.default_revs = m.default_revs
        super().__init__()
    
class Format_Acorn_ADFS_1600(Format):
    img_compatible = True
    def __init__(self):
        import greaseweazle.codec.ibm.mfm as m
        self.fmt = m.Acorn_ADFS_1600
        self.default_revs = m.default_revs
        super().__init__()
    
class Format_Amiga_AmigaDOS_DD(Format):
    adf_compatible = True
    def __init__(self):
        import greaseweazle.codec.amiga.amigados as m
        self.fmt = m.AmigaDOS_DD
        self.default_revs = m.default_revs
        super().__init__()
    
class Format_Amiga_AmigaDOS_HD(Format):
    adf_compatible = True
    def __init__(self):
        import greaseweazle.codec.amiga.amigados as m
        self.fmt = m.AmigaDOS_HD
        self.default_revs = m.default_revs
        super().__init__()
    
class Format_Commodore_1581(Format):
    img_compatible = True
    def __init__(self):
        import greaseweazle.codec.ibm.mfm as m
        self.fmt = m.Commodore_1581
        self.default_revs = m.default_revs
        super().__init__()
    
class Format_IBM_180(Format):
    img_compatible = True
    default_trackset = 'c=0-39:h=0'
    max_trackset = 'c=0-41:h=0'
    def __init__(self):
        import greaseweazle.codec.ibm.mfm as m
        self.fmt = m.IBM_MFM_720
        self.default_revs = m.default_revs
        super().__init__()
    
class Format_IBM_360(Format):
    img_compatible = True
    default_trackset = 'c=0-39:h=0-1'
    max_trackset = 'c=0-41:h=0-1'
    def __init__(self):
        import greaseweazle.codec.ibm.mfm as m
        self.fmt = m.IBM_MFM_720
        self.default_revs = m.default_revs
        super().__init__()
    
class Format_IBM_720(Format):
    img_compatible = True
    def __init__(self):
        import greaseweazle.codec.ibm.mfm as m
        self.fmt = m.IBM_MFM_720
        self.default_revs = m.default_revs
        super().__init__()
    
class Format_IBM_1200(Format):
    img_compatible = True
    def __init__(self):
        import greaseweazle.codec.ibm.mfm as m
        self.fmt = m.IBM_MFM_1200
        self.default_revs = m.default_revs
        super().__init__()

class Format_IBM_1440(Format):
    img_compatible = True
    def __init__(self):
        import greaseweazle.codec.ibm.mfm as m
        self.fmt = m.IBM_MFM_1440
        self.default_revs = m.default_revs
        super().__init__()

class Format_IBM_1680(Format):
    img_compatible = True
    def __init__(self):
        import greaseweazle.codec.ibm.mfm as m
        self.fmt = m.IBM_MFM_1680
        self.default_revs = m.default_revs
        super().__init__()

class Format_Atari_90(Format):
    img_compatible = True
    default_trackset = 'c=0-39:h=0:step=2'
    max_trackset = 'c=0-41:h=0:step=2'
    def __init__(self):
        import greaseweazle.codec.ibm.fm as m
        self.fmt = m.Atari_90
        self.default_revs = m.default_revs
        super().__init__()

class Format_AtariST_360(Format):
    img_compatible = True
    default_trackset = 'c=0-79:h=0'
    max_trackset = 'c=0-81:h=0'
    def __init__(self):
        import greaseweazle.codec.ibm.mfm as m
        self.fmt = m.AtariST_SS_9SPT
        self.default_revs = m.default_revs
        super().__init__()
    
class Format_AtariST_400(Format):
    img_compatible = True
    default_trackset = 'c=0-79:h=0'
    max_trackset = 'c=0-81:h=0'
    def __init__(self):
        import greaseweazle.codec.ibm.mfm as m
        self.fmt = m.AtariST_10SPT
        self.default_revs = m.default_revs
        super().__init__()
    
class Format_AtariST_440(Format):
    img_compatible = True
    default_trackset = 'c=0-79:h=0'
    max_trackset = 'c=0-81:h=0'
    def __init__(self):
        import greaseweazle.codec.ibm.mfm as m
        self.fmt = m.AtariST_11SPT
        self.default_revs = m.default_revs
        super().__init__()
    
class Format_AtariST_720(Format):
    img_compatible = True
    def __init__(self):
        import greaseweazle.codec.ibm.mfm as m
        self.fmt = m.AtariST_DS_9SPT
        self.default_revs = m.default_revs
        super().__init__()
    
class Format_AtariST_800(Format):
    img_compatible = True
    def __init__(self):
        import greaseweazle.codec.ibm.mfm as m
        self.fmt = m.AtariST_10SPT
        self.default_revs = m.default_revs
        super().__init__()
    
class Format_AtariST_880(Format):
    img_compatible = True
    def __init__(self):
        import greaseweazle.codec.ibm.mfm as m
        self.fmt = m.AtariST_11SPT
        self.default_revs = m.default_revs
        super().__init__()
    
class Format_Ensoniq_800(Format):
    img_compatible = True
    def __init__(self):
        import greaseweazle.codec.ibm.mfm as m
        self.fmt = m.Ensoniq_800
        self.default_revs = m.default_revs
        super().__init__()

class Format_Ensoniq_1600(Format):
    img_compatible = True
    def __init__(self):
        import greaseweazle.codec.ibm.mfm as m
        self.fmt = m.Ensoniq_1600
        self.default_revs = m.default_revs
        super().__init__()

class Format_Sega_SF7000(Format):
    img_compatible = True
    default_trackset = 'c=0-39:h=0'
    max_trackset = 'c=0-81:h=0'
    def __init__(self):
        import greaseweazle.codec.ibm.mfm as m
        self.fmt = m.Sega_SF7000
        self.default_revs = m.default_revs
        super().__init__()

    
formats = OrderedDict({
    'acorn.dfs.ss': Format_Acorn_DFS_SS,
    'acorn.dfs.ds': Format_Acorn_DFS_DS,
    'acorn.adfs.160': Format_Acorn_ADFS_160,
    'acorn.adfs.320': Format_Acorn_ADFS_320,
    'acorn.adfs.640': Format_Acorn_ADFS_640,
    'acorn.adfs.800': Format_Acorn_ADFS_800,
    'acorn.adfs.1600': Format_Acorn_ADFS_1600,
    'amiga.amigados': Format_Amiga_AmigaDOS_DD,
    'amiga.amigados_hd': Format_Amiga_AmigaDOS_HD,
    'atari.90': Format_Atari_90,
    'atarist.360': Format_AtariST_360,
    'atarist.400': Format_AtariST_400,
    'atarist.440': Format_AtariST_440,
    'atarist.720': Format_AtariST_720,
    'atarist.800': Format_AtariST_800,
    'atarist.880': Format_AtariST_880,
    'commodore.1581': Format_Commodore_1581,
    'ensoniq.800': Format_Ensoniq_800,
    'ensoniq.1600': Format_Ensoniq_1600,
    'ibm.180': Format_IBM_180,
    'ibm.360': Format_IBM_360,
    'ibm.720': Format_IBM_720,
    'ibm.1200': Format_IBM_1200,
    'ibm.1440': Format_IBM_1440,
    'ibm.1680': Format_IBM_1680,
    'ibm.dmf': Format_IBM_1680,
    'sega.sf7000': Format_Sega_SF7000,
})

def print_formats(f = None):
    s = ''
    for k, v in formats.items():
        if not f or f(k, v):
            if s:
                s += '\n'
            s += '  ' + k
    return s
