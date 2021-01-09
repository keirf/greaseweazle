# greaseweazle/image/kryoflux.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import struct, re, math, os
import itertools as it

from greaseweazle import error
from greaseweazle.flux import Flux
from .image import Image

mck = 18432000 * 73 / 14 / 2
sck = mck / 2

class Op:
    Nop1  =  8
    Nop2  =  9
    Nop3  = 10
    Ovl16 = 11
    Flux3 = 12
    OOB   = 13

class OOB:
    StreamInfo =  1
    Index      =  2
    StreamEnd  =  3
    KFInfo     =  4
    EOF        = 13

class KryoFlux(Image):

    def __init__(self, name):
        if os.path.isdir(name):
            self.basename = os.path.join(name, '')
        else:
            m = re.search("(\d{2}.[01])?.raw$", name)
            self.basename = name[:m.start()]


    @classmethod
    def to_file(cls, name):
        return cls(name)

    @classmethod
    def from_file(cls, name):
        return cls(name)


    def get_track(self, cyl, side):

        name = self.basename + '%02d.%d.raw' % (cyl, side)
        try:
            with open(name, 'rb') as f:
                dat = f.read()
        except FileNotFoundError:
            return None

        # Parse the index-pulse stream positions.
        index = []
        idx = 0
        while idx < len(dat):
            op = dat[idx]
            if op == Op.OOB:
                oob_op, oob_sz = struct.unpack('<BH', dat[idx+1:idx+4])
                idx += 4
                if oob_op == OOB.Index:
                    pos, = struct.unpack('<I', dat[idx:idx+4])
                    index.append(pos)
                elif oob_op == OOB.EOF:
                    break
                idx += oob_sz
            elif op == Op.Nop3 or op == Op.Flux3:
                idx += 3
            elif op <= 7 or op == Op.Nop2:
                idx += 2
            else:
                idx += 1

        # Build the flux and index lists for the Flux object.
        flux, flux_list, index_list = [], [], []
        val, index_idx, stream_idx, idx = 0, 0, 0, 0
        while idx < len(dat):
            if index_idx < len(index) and stream_idx >= index[index_idx]:
                # We've passed an index marker.
                index_list.append(sum(flux))
                flux_list += flux
                flux = []
                index_idx += 1
            op = dat[idx]
            if op <= 7:
                # Flux2
                val += (op << 8) + dat[idx+1]
                flux.append(val)
                val = 0
                stream_idx += 2
                idx += 2
            elif op <= 10:
                # Nop1, Nop2, Nop3
                nr = op-7
                stream_idx += nr
                idx += nr
            elif op == Op.Ovl16:
                # Ovl16
                val += 0x10000
                stream_idx += 1
                idx += 1
            elif op == Op.Flux3:
                # Flux3
                val += (dat[idx+1] << 8) + dat[idx+2]
                flux.append(val)
                val = 0
                stream_idx += 3
                idx += 3
            elif op == Op.OOB:
                # OOB
                oob_op, oob_sz = struct.unpack('<BH', dat[idx+1:idx+4])
                idx += 4
                if oob_op == OOB.StreamInfo or oob_op == OOB.StreamEnd:
                    pos, = struct.unpack('<I', dat[idx:idx+4])
                    error.check(pos == stream_idx,
                                "Out-of-sync during KryoFlux stream read")
                elif oob_op == OOB.EOF:
                    break
                idx += oob_sz
            else:
                # Flux1
                val += op
                flux.append(val)
                val = 0
                stream_idx += 1
                idx += 1

        flux_list += flux

        # Crop partial first revolution.
        if len(index_list) > 1:
            short_index, index_list = index_list[0], index_list[1:]
            flux = 0
            for i in range(len(flux_list)):
                if flux >= short_index:
                    break
                flux += flux_list[i]
            flux_list = flux_list[i:]

        return Flux(index_list, flux_list, sck)


    def emit_track(self, cyl, side, track):
        """Converts @track into a KryoFlux stream file."""

        # Check if we should insert an OOB record for the next index mark.
        def check_index(prev_flux):
            nonlocal index_idx, dat
            if index_idx < len(index) and total >= index[index_idx]:
                dat += struct.pack('<2BH3I', Op.OOB, OOB.Index, 12,
                                   stream_idx,
                                   round(index[index_idx] - total + prev_flux),
                                   round(index[index_idx]/8))
                index_idx += 1

        # Emit a resampled flux value to the KryoFlux data stream.
        def emit(f):
            nonlocal stream_idx, dat, total
            while f >= 0x10000:
                stream_idx += 1
                dat.append(Op.Ovl16)
                f -= 0x10000
                total += 0x10000
                check_index(0x10000)
            if f >= 0x800:
                stream_idx += 3
                dat += struct.pack('>BH', Op.Flux3, f)
            elif Op.OOB < f < 0x100:
                stream_idx += 1
                dat.append(f)
            else:
                stream_idx += 2
                dat += struct.pack('>H', f)
            total += f
            check_index(f)

        flux = track.flux()
        factor = sck / flux.sample_freq
        dat = bytearray()

        # Start the data stream with a dummy index if our Flux is index cued.
        if flux.index_cued:
            dat += struct.pack('<2BH3I', Op.OOB, OOB.Index, 12, 0, 0, 0)

        # Prefix-sum list of resampled index timings.
        index = list(it.accumulate(map(lambda x: x*factor, flux.index_list)))
        index_idx = 0
        
        stream_idx, total, rem = 0, 0, 0.0
        for x in flux.list:
            y = x * factor + rem
            f = round(y)
            rem = y - f
            emit(f)

        # We may not have enough flux to get to the final index value.
        # Generate a dummy flux just enough to get us there.
        if index_idx < len(index):
            emit(math.ceil(index[index_idx] - total) + 1)
        # A dummy cell so that we definitely have *something* after the
        # final OOB.Index, so that all parsers should register the Index.
        emit(round(sck*12e-6)) # 12us

        # Emit StreamEnd and EOF blocks to terminate the stream.
        dat += struct.pack('<2BH2I', Op.OOB, OOB.StreamEnd, 8, stream_idx, 0)
        dat += struct.pack('<2BH', Op.OOB, OOB.EOF, 0x0d0d)

        name = self.basename + '%02d.%d.raw' % (cyl, side)
        with open(name, 'wb') as f:
                f.write(dat)


    def __enter__(self):
        return self
    def __exit__(self, type, value, tb):
        pass


# Local variables:
# python-indent: 4
# End:
