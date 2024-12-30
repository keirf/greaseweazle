# greaseweazle/image/caps.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
# 
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from __future__ import annotations
from typing import cast, List, Tuple, Optional, Generator

import os, sys
import platform
import ctypes as ct
import itertools as it
from bitarray import bitarray
from greaseweazle.track import MasterTrack, PLLTrack
from greaseweazle.flux import Flux
from greaseweazle import error
from .image import Image, OptDict

class CapsDateTimeExt(ct.Structure):
    _pack_ = 1
    _fields_ = [
        ('year',  ct.c_uint),
        ('month', ct.c_uint),
        ('day',   ct.c_uint),
        ('hour',  ct.c_uint),
        ('min',   ct.c_uint),
        ('sec',   ct.c_uint),
        ('tick',  ct.c_uint)]

class CapsImageInfo(ct.Structure):
    platform_name = [
        "N/A", "Amiga", "Atari ST", "IBM PC", "Amstrad CPC",
        "Spectrum", "Sam Coupe", "Archimedes", "C64", "Atari (8-bit)" ]
    _pack_ = 1
    _fields_ = [
        ('type',        ct.c_uint), # image type
        ('release',     ct.c_uint), # release ID
        ('revision',    ct.c_uint), # release revision ID
        ('mincylinder', ct.c_uint), # lowest cylinder number
        ('maxcylinder', ct.c_uint), # highest cylinder number
        ('minhead',     ct.c_uint), # lowest head number
        ('maxhead',     ct.c_uint), # highest head number
        ('crdt',        CapsDateTimeExt), # image creation date.time
        ('platform',    ct.c_uint * 4)] # intended platform(s)

class CapsTrackInfoT2(ct.Structure):
    _pack_ = 1
    _fields_ = [
        ('type',       ct.c_uint), # track type
        ('cylinder',   ct.c_uint), # cylinder#
        ('head',       ct.c_uint), # head#
        ('sectorcnt',  ct.c_uint), # available sectors
        ('sectorsize', ct.c_uint), # sector size, unused
        ('trackbuf',   ct.POINTER(ct.c_ubyte)), # track buffer memory 
        ('tracklen',   ct.c_uint), # track buffer memory length
        ('timelen',    ct.c_uint), # timing buffer length
        ('timebuf',    ct.POINTER(ct.c_uint)), # timing buffer
        ('overlap',    ct.c_int),  # overlap position
        ('startbit',   ct.c_uint), # start position of the decoding
        ('wseed',      ct.c_uint), # weak bit generator data
        ('weakcnt',    ct.c_uint)] # number of weak data areas

class CapsSectorInfo(ct.Structure):
    _pack_ = 1
    _fields_ = [
        ('descdatasize', ct.c_uint), # data size in bits from IPF descriptor
        ('descgapsize', ct.c_uint),  # gap size in bits from IPF descriptor
        ('datasize', ct.c_uint),     # data size in bits from decoder
        ('gapsize', ct.c_uint),      # gap size in bits from decoder
        ('datastart', ct.c_uint),    # data start pos in bits from decoder
        ('gapstart', ct.c_uint),     # gap start pos in bits from decoder
        ('gapsizews0', ct.c_uint),   # gap size before write splice
        ('gapsizews1', ct.c_uint),   # gap size after write splice
        ('gapws0mode', ct.c_uint),   # gap size mode before write splice
        ('gapws1mode', ct.c_uint),   # gap size mode after write splice
        ('celltype', ct.c_uint),     # bitcell type
        ('enctype', ct.c_uint)]      # encoder type

class CapsDataInfo(ct.Structure):
    _pack_ = 1
    _fields_ = [
        ('type', ct.c_uint),  # data type
        ('start', ct.c_uint), # start position
        ('size', ct.c_uint)]  # size in bits

class DI_LOCK:
    INDEX     = 1<<0
    ALIGN     = 1<<1
    DENVAR    = 1<<2
    DENAUTO   = 1<<3
    DENNOISE  = 1<<4
    NOISE     = 1<<5
    NOISEREV  = 1<<6
    MEMREF    = 1<<7
    UPDATEFD  = 1<<8
    TYPE      = 1<<9
    DENALT    = 1<<10
    OVLBIT    = 1<<11
    TRKBIT    = 1<<12
    NOUPDATE  = 1<<13
    SETWSEED  = 1<<14
    def_flags = (DENVAR | UPDATEFD | NOUPDATE | TYPE | OVLBIT | TRKBIT)

RangeList = List[Tuple[int,int]]

class CAPSTrackInfo(CapsTrackInfoT2):

    class NoTrack(Exception):
        pass

    def __init__(self, image: CAPS, cyl: int, head: int) -> None:
        pi = image.pi
        if head < pi.minhead or head > pi.maxhead:
            raise CAPSTrackInfo.NoTrack()
        if cyl < pi.mincylinder or cyl > pi.maxcylinder:
            raise CAPSTrackInfo.NoTrack()

        ti = self
        CapsTrackInfoT2.__init__(ti, 2)
        res = image.lib.CAPSLockTrack(ct.byref(ti), image.iid,
                                      cyl, head, DI_LOCK.def_flags)
        error.check(res == 0, "Could not lock CAPS track %d.%d" % (cyl, head))

        if not ti.trackbuf:
            raise CAPSTrackInfo.NoTrack() # unformatted/empty

        carray_type = ct.c_ubyte * ((ti.tracklen+7)//8)
        carray = carray_type.from_address(
            ct.addressof(ti.trackbuf.contents))
        bits = bitarray(endian='big')
        bits.frombytes(bytes(carray))
        bits = bits = bits[:ti.tracklen]

        ticks: Optional[List[float]] = None
        if ti.timebuf:
            carray_type = ct.c_uint * ti.timelen
            carray = carray_type.from_address(
                ct.addressof(ti.timebuf.contents))
            # Unpack the per-byte timing info into per-bitcell
            ticks = []
            for i in carray:
                for j in range(8):
                    ticks.append(i)
            # Pad the timing info with normal cell lengths as necessary
            for j in range(len(carray)*8, ti.tracklen):
                ticks.append(1000)
            # Clip the timing info, if necessary.
            ticks = ticks = ticks[:ti.tracklen]

        ti.bits = bits
        ti.ticks = ticks

        # We don't really have access to the bitrate. It depends on RPM.
        # So we assume a rotation rate of 300 RPM (5 rev/sec).
        ti.rpm = 300


class CAPS(Image):

    iid: int
    pi: CapsImageInfo
    imagetype: str

    read_only = True

    def __init__(self, name: str, _fmt) -> None:
        self.filename = name
        self.lib = get_libcaps()

    def __del__(self) -> None:
        try:
            self.lib.CAPSUnlockAllTracks(self.iid)
            self.lib.CAPSUnlockImage(self.iid)
            self.lib.CAPSRemImage(self.iid)
            del(self.iid)
        except AttributeError:
            pass

    def __str__(self) -> str:
        raise NotImplementedError

    def get_track(self, cyl: int, head: int) -> Optional[MasterTrack]:
        raise NotImplementedError

    @classmethod
    def from_file(cls, name: str, _fmt, opts: OptDict) -> Image:

        caps = cls(name, _fmt)
        caps.apply_r_opts(opts)
        errprefix = f'CAPS: {cls.imagetype}'

        caps.iid = caps.lib.CAPSAddImage()
        error.check(caps.iid >= 0,
                    f"{errprefix}: Could not create image container")
        cname = ct.c_char_p(name.encode())
        res = caps.lib.CAPSLockImage(caps.iid, cname)
        error.check(res == 0,
                    f"{errprefix}: Could not open image '{name}'")
        res = caps.lib.CAPSLoadImage(caps.iid, DI_LOCK.def_flags)
        error.check(res == 0,
                    f"{errprefix}: Could not load image '%s'" % name)
        caps.pi = CapsImageInfo()
        res = caps.lib.CAPSGetImageInfo(ct.byref(caps.pi), caps.iid)
        error.check(res == 0,
                    f"{errprefix}: Could not get info for image '{name}'")
        print(caps)

        return caps


class CTRaw(CAPS):

    imagetype = 'CTRaw'

    def __str__(self) -> str:
        pi = self.pi
        s = "CTRaw Image File:"
        s += ("\n Cyls: %d-%d  Heads: %d-%d"
              % (pi.mincylinder, pi.maxcylinder, pi.minhead, pi.maxhead))
        return s

    def get_track(self, cyl: int, head: int) -> Optional[MasterTrack]:

        try:
            ti = CAPSTrackInfo(self, cyl, head)
        except CAPSTrackInfo.NoTrack:
            return None

        # CTRaw dumps get bogus speed info from the CAPS library.
        # Assume they are uniform density.
        bit_ticks = None # ti.ticks

        return MasterTrack(
            bits = ti.bits,
            time_per_rev = 60/ti.rpm,
            bit_ticks = bit_ticks)


class IPFTrack(MasterTrack):

    verify_revs: float = 2
    tolerance = 100

    sectors: RangeList

    @staticmethod
    def strong_data(sector: RangeList, weak: RangeList) -> Generator:
        """Return list of sector data areas excluding weak sections."""
        def range_next(i):
            s,l = next(i)
            return s, s+l
        weak_tol = 16 # Skip this number of bits after a weak area
        weak_iter = it.chain(weak, [(1<<30,1)])
        ws,we = -1,-1
        sector_iter = iter(sector)
        s,e = range_next(sector_iter)
        try:
            while True:
                while we <= s:
                    ws,we = range_next(weak_iter)
                    we += weak_tol
                if ws < e:
                    if s < ws:
                        yield (s,ws-s)
                    s = we
                else:
                    yield (s,e-s)
                    s = e
                if s >= e:
                    s,e = range_next(sector_iter)
        except StopIteration:
            pass

    def verify_track(self, flux: Flux) -> bool:
        flux.cue_at_index()
        raw = PLLTrack(clock = self.time_per_rev/len(self.bits), data = flux)
        raw_bits, _ = raw.get_all_data()
        for s,l in IPFTrack.strong_data(self.sectors, self.weak):
            sector = self.bits[s:s+l]
            # Search within an area +/- the pre-defined # bitcells tolerance
            raw_area = raw_bits[max(self.splice + s - self.tolerance, 0)
                                : self.splice + s + l + self.tolerance]
            # All we care about is at least one match (this is a bit fuzzy)
            if next(raw_area.search(sector), None) is None:
                return False
        return True


class IPF(CAPS):

    imagetype = 'IPF'

    def __str__(self) -> str:
        pi = self.pi
        s = "IPF Image File:"
        if pi.release == 0x843265bb: # disk-utilities:IPF_ID
            s += "\n SPS ID: None (https://github.com/keirf/disk-utilities)"
        else:
            s += "\n SPS ID: %04d (rev %d)" % (pi.release, pi.revision)
        s += "\n Platform: "
        nr_platforms = 0
        for p in pi.platform:
            if p == 0 and nr_platforms != 0:
                break
            if nr_platforms > 0:
                s += ", "
            s += pi.platform_name[p]
            nr_platforms += 1
        s += ("\n Created: %d/%d/%d %02d:%02d:%02d"
             % (pi.crdt.year, pi.crdt.month, pi.crdt.day,
                pi.crdt.hour, pi.crdt.min, pi.crdt.sec))
        s += ("\n Cyls: %d-%d  Heads: %d-%d"
              % (pi.mincylinder, pi.maxcylinder, pi.minhead, pi.maxhead))
        return s

    def get_track(self, cyl: int, head: int) -> Optional[MasterTrack]:

        try:
            ti = CAPSTrackInfo(self, cyl, head)
        except CAPSTrackInfo.NoTrack:
            return None

        data = []
        for i in range(ti.sectorcnt):
            si = CapsSectorInfo()
            res = self.lib.CAPSGetInfo(ct.byref(si), self.iid,
                                       cyl, head, 1, i)
            error.check(res == 0, "Couldn't get sector info")
            # Adjust the range start to be splice- rather than index-relative
            data.append((si.datastart % ti.tracklen, si.datasize))

        weak = []
        for i in range(ti.weakcnt):
            wi = CapsDataInfo()
            res = self.lib.CAPSGetInfo(ct.byref(wi), self.iid,
                                       cyl, head, 2, i)
            error.check(res == 0, "Couldn't get weak data info")
            # Adjust the range start to be splice- rather than index-relative
            weak.append((wi.start % ti.tracklen, wi.size))

        if ti.overlap < 0 and weak:
            # Splice halfway through the longest weak area.
            longest_weak = 0
            for i,(s,n) in enumerate(weak):
                if n > weak[longest_weak][1]:
                    longest_weak = i
            s,n = weak[longest_weak]
            if n > 200:
                ti.overlap = (s + n//2) % ti.tracklen

        if ti.overlap < 0 and data:
            # Splice halfway through the longest gap area.
            data.sort()
            gap = []
            for i,(s,n) in enumerate(data):
                gap.append((data[(i+1)%len(data)][0] - s - n) % ti.tracklen)
            i = gap.index(max(gap))
            s,n = data[i]
            ti.overlap = (s + n + gap[i] // 2) % ti.tracklen

        if ti.overlap < 0:
                # No sector or weak information. Splice at the index.
                ti.overlap = 0

        if ti.overlap:

            # Adjust range starts to be splice- rather than index-relative
            f = lambda x: ((x[0] - ti.overlap) % ti.tracklen, x[1])
            data = list(map(f, data))
            weak = list(map(f, weak))

            # Rotate the track to start at the splice rather than the index.
            ti.bits = ti.bits[ti.overlap:] + ti.bits[:ti.overlap]
            if ti.ticks:
                ti.ticks = ti.ticks[ti.overlap:] + ti.ticks[:ti.overlap]

        # Sort ranges by start, and clip at splice point.
        def clip_and_sort_ranges(r):
            res = []
            for i,(s,n) in enumerate(r):
                if s + n > ti.tracklen:
                    res.append((s,ti.tracklen-s))
                    res.append((0, s+n-ti.tracklen))
                else:
                    res.append((s,n))
            res.sort()
            return res
        data = clip_and_sort_ranges(data)
        weak = clip_and_sort_ranges(weak)

        track = IPFTrack(
            bits = ti.bits,
            time_per_rev = 60/ti.rpm,
            bit_ticks = ti.ticks,
            splice = ti.overlap,
            weak = weak
        )
        track.verify = track
        track.sectors = data
        return track


# Open and initialise the CAPS library.
def open_libcaps():

    # Get the OS-dependent list of valid CAPS library names.
    _names = []
    if platform.system() == "Linux":
        _names = [ "libcapsimage.so.5", "libcapsimage.so.5.1",
                   "libcapsimage.so.4", "libcapsimage.so.4.2",
                   "libcapsimage.so" ]
    elif platform.system() == "Darwin":
        _names = [ "CAPSImage.framework/CAPSImage",
                   "CAPSImg.framework/CAPSImg" ]
    elif platform.system() == "Windows":
        _names = [ "CAPSImg_x64.dll", "CAPSImg.dll" ]

    # Get the absolute path to the root Greaseweazle folder.
    path = os.path.dirname(os.path.abspath(__file__))
    for _ in range(3):
        path = os.path.join(path, os.pardir)
    path = os.path.normpath(path)

    # Create a search list of both relative and absolute library names.
    names = []
    for name in _names:
        names.append(name)
        names.append(os.path.join(path, name))
        if platform.system() == "Darwin":
            names.append(os.path.join('/Library/Frameworks', name))

    # Walk the search list, trying to open the CAPS library.
    for name in names:
        try:
            lib = ct.cdll.LoadLibrary(name)
            break
        except:
            pass
    
    error.check("lib" in locals(), """\
Could not find SPS/CAPS library
For installation instructions please read the wiki:
<https://github.com/keirf/greaseweazle/wiki/IPF-Images>""")
    
    # We have opened the library. Now initialise it.
    res = lib.CAPSInit()
    error.check(res == 0, "Failure initialising CAPS/SPS library '%s'" % name)

    return lib


# Get a reference to the CAPS library. Open it if necessary.
def get_libcaps():
    global libcaps
    if not 'libcaps' in globals():
        libcaps = open_libcaps()
    return libcaps


# Local variables:
# python-indent: 4
# End:
