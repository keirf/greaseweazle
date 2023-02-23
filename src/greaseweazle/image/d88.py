# greaseweazle/image/d88.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from typing import Dict, Tuple, Optional, List

import struct
import os

from greaseweazle import error
from greaseweazle.codec.formats import *
from greaseweazle.codec.ibm import ibm
from .image import Image

from greaseweazle.codec import formats

class D88(Image):

    read_only = True

    def __init__(self, name: str):
        self.to_track: Dict[Tuple[int,int],ibm.IBMTrackFormatted] = dict()
        self.filename = name

    @classmethod
    def from_file(cls, name: str) -> Image:

        with open(name, "rb") as f:
            header = f.read(32)
            (disk_name, terminator, write_protect, media_flag, disk_size) = struct.unpack('<16sB9xBBL', header)
            track_table = [x[0] for x in struct.iter_unpack('<L', f.read(640))]
            if track_table[0] == 688:
                track_table.extend([x[0] for x in struct.iter_unpack('<L', f.read(16))])
            elif track_table[0] != 672:
                raise error.Fatal("D88: Unsupported track table length.")
            f.seek(0, os.SEEK_END)
            if f.tell() != disk_size:
                print('D88: Warning: Multiple disks found in image, only using first.')

            d88 = cls(name)

            for track_index, track_offset in enumerate(track_table):
                if track_offset == 0:
                    continue
                f.seek(track_offset)
                if f.tell() >= disk_size:
                    continue
                cyl = track_index // 2
                head = track_index % 2
                track = None
                track_mfm_flag = None
                pos = None
                secs: List[Tuple[int,int,int,int,bytes]] = []
                num_sectors_track = 255
                while len(secs) < num_sectors_track:
                    (c, h, r, n, num_sectors, mfm_flag,
                     deleted, status, data_size) = \
                        struct.unpack('<BBBBHBBB5xH', f.read(16))
                    if status != 0x00:
                        raise error.Fatal('D88: FDC error codes are unsupported.')
                    if deleted != 0x00:
                        raise error.Fatal('D88: Deleted data is unsupported.')
                    if track is None:
                        if media_flag == 0x00:

                            if mfm_flag == 0x40:
                                track = ibm.IBMTrackFormat('ibm.fm')
                                track.rate = 125
                            else:
                                track = ibm.IBMTrackFormat('ibm.mfm')
                                track.rate = 250
                            track.rpm = 300
                        else:
                            if mfm_flag == 0x40:
                                track = ibm.IBMTrackFormat('ibm.fm')
                                track.rate = 250
                            else:
                                track = ibm.IBMTrackFormat('ibm.mfm')
                                track.rate = 500
                            track.rpm = 360
                        track_mfm_flag = mfm_flag
                        num_sectors_track = num_sectors
                    if mfm_flag != track_mfm_flag:
                        raise error.Fatal('D88: Mixed FM and MFM sectors in one track are unsupported.')
                    if num_sectors_track != num_sectors:
                        raise error.Fatal('D88: Corrupt number of sectors per track in sector header.')
                    data = f.read(data_size)
                    size = 128 << n
                    if size != data_size:
                        raise error.Fatal('D88: Extra sector data is unsupported.')
                    secs.append((c,h,r,n,data))
                if track is None:
                    continue
                track.secs = len(secs)
                track.sz = [x[3] for x in secs]
                track.finalise()
                t = track.mk_track(cyl, head)

                for nr,s in enumerate(t.sectors):
                    c,h,r,n,data = secs[nr]
                    s.crc = s.idam.crc = s.dam.crc = 0
                    s.idam.c, s.idam.h, s.idam.r, s.idam.n = c,h,r,n
                    s.dam.data = data

                d88.to_track[cyl, head] = t

        return d88

    def get_track(self, cyl: int, side: int) -> Optional[ibm.IBMTrackFormatted]:
        if (cyl,side) not in self.to_track:
            return None
        return self.to_track[cyl,side]

# Local variables:
# python-indent: 4
# End:
