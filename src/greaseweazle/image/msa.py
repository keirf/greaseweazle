# greaseweazle/image/msa.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from typing import Dict, Tuple, Optional

import struct

from greaseweazle import error
from greaseweazle.codec.ibm import ibm
from .image import Image

class MSA(Image):

    def __init__(self, name: str, _fmt):
        self.to_track: Dict[Tuple[int,int],ibm.IBMTrack_Fixed] = dict()
        self.filename = name


    def from_bytes(self, dat: bytes) -> None:

        id, spt, nsides, st, et = struct.unpack('>2s4H', dat[0:10])

        error.check(id == b'\x0e\x0f', 'MSA: Unrecognised signature')

        nsides += 1 
        error.check(1 <= nsides <= 2, f'MSA: Bad number of sides: {nsides}')

        idx = 10
        for cyl in range(st, et+1):
            for head in range(nsides):
                nbytes, = struct.unpack('>H', dat[idx:idx+2])
                error.check(nbytes <= spt*512, 'MSA: Track data too long')
                idx += 2
                td = dat[idx:idx+nbytes]
                idx += nbytes

                if nbytes == spt*512:
                    tdat = td
                else:
                    tdat = bytearray()
                    tidx = 0
                    while tidx < len(td):
                        b, tidx = td[tidx], tidx+1
                        if b == 0xe5:
                            b, runlen = struct.unpack('>BH', td[tidx:tidx+3])
                            tidx += 3
                            tdat += bytes([b]) * runlen
                        else:
                            tdat.append(b)
                    error.check(len(tdat) == spt*512,
                                'MSA: Bad track compressed data')

                track = ibm.IBMTrack_FixedDef('ibm.mfm')
                track.iam = False
                track.rate = 250
                track.rpm = 300
                track.secs = spt
                track.sz = [2]
                if spt <= 9:
                    track.gap3 = 84
                    track.cskew = 4
                    track.hskew = 2
                elif spt == 10:
                    track.gap3 = 30
                else:
                    track.gap3 = 3
                    track.rate = 261
                track.finalise()
                t = track.mk_track(cyl, head)

                for n,s in enumerate(t.sectors):
                    s.crc = s.idam.crc = s.dam.crc = 0
                    s.idam.c, s.idam.h, s.idam.r, s.idam.n = cyl, head, n+1, 2
                    s.dam.data = tdat[n*512:(n+1)*512]

                self.to_track[cyl, head] = t


    def get_track(self, cyl: int, side: int) -> Optional[ibm.IBMTrack_Fixed]:
        if (cyl,side) not in self.to_track:
            return None
        return self.to_track[cyl,side]


    def emit_track(self, cyl: int, side: int, track) -> None:
        self.to_track[cyl,side] = track


    def get_image(self) -> bytes:

        n_side = max(self.to_track.keys(), default=(0,0), key=lambda x:x[1])[1]
        n_side += 1
        st = min(self.to_track.keys(), default=(0,), key=lambda x:x[0])[0]
        et = max(self.to_track.keys(), default=(0,), key=lambda x:x[0])[0]
        
        dat = bytearray()
        spt = None
        
        for c in range(st,et+1):
            for h in range(n_side):

                # Grab the IBM MFM track data. Perform sanity checks.
                error.check((c,h) in self.to_track,
                            f'MSA: Missing track {c}.{h} in output')
                track = self.to_track[c,h]
                error.check(isinstance(track, ibm.IBMTrack_Fixed),
                            f'MSA: Track {c}.{h} is not an IBM track: '
                            'Maybe missing --format= option?')
                tdat = track.get_img_track()
                if spt is None:
                    spt = len(track.sectors)
                error.check(spt == len(track.sectors),
                            f'MSA: Track {c}.{h} has incorrect sectors per '
                            f'track ({spt} != {len(track.sectors)})')

                # Compress the track data.
                td = bytearray()
                tidx, runlen, runbyte = 0, 0, 0
                while tidx < len(tdat):
                    b, tidx = tdat[tidx], tidx+1
                    if b != runbyte:
                        if runlen < 4 and runbyte != 0xe5:
                            td += bytes([runbyte]) * runlen
                        elif runlen != 0:
                            td += struct.pack('>2BH', 0xe5, runbyte, runlen)
                        runlen = 0
                    runbyte = b
                    runlen += 1
                if runlen < 4 and runbyte != 0xe5:
                    td += bytes([runbyte]) * runlen
                elif runlen != 0:
                    td += struct.pack('>2BH', 0xe5, runbyte, runlen)

                # Use the compressed data if it's shorter than raw data.
                if len(td) < len(tdat):
                    dat += struct.pack('>H', len(td))
                    dat += td
                else:
                    dat += struct.pack('>H', len(tdat))
                    dat += tdat

        header = struct.pack('>2s4H', b'\x0e\x0f', spt, n_side-1, st, et)

        return header + dat


# Local variables:
# python-indent: 4
# End:
