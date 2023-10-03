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
from greaseweazle.codec.ibm import ibm
from .image import Image

class D88(Image):

    read_only = True

    def __init__(self, name: str):
        self.to_track: Dict[Tuple[int,int],ibm.IBMTrack_Fixed] = dict()
        self.filename = name

    @staticmethod
    def remove_duplicate_sectors(secs) ->  List[Tuple[int,int,int,int,bytes]]:
        new_secs: List[Tuple[int,int,int,int,bytes]] = []
        for s in secs:
            dup = False
            for t in new_secs:
                if s == t:
                    dup = True
                    break
            if not dup:
                new_secs.append(s)
        return new_secs

    @classmethod
    def from_file(cls, name: str, _fmt, index: int = -1) -> Image:

        with open(name, "rb") as f:
            f.seek(0, os.SEEK_END)
            file_size = f.tell()
            f.seek(0)
            disk_offsets: List[int] = []
            current_disk_index = 0
            while 1:
                disk_offsets.append(f.tell())
                header = struct.unpack('<16sB9xBBL', f.read(32))
                _, _, _, _, disk_size = header
                if f.tell() + disk_size >= file_size:
                    break
                f.seek(disk_offsets[current_disk_index] + disk_size)
                current_disk_index += 1

            if index < 0 and len(disk_offsets) > 1:
                print('D88: Warning: Multiple disks found in image, '
                      'only using first.')
                index = 0
            if index >= len(disk_offsets):
                raise error.Fatal("D88: No disk with index %d in image file."
                                  % index)

            f.seek(disk_offsets[index])
            header = struct.unpack('<16sB9xBBL', f.read(32))
            disk_name, terminator, write_prot, media_flag, disk_size = header
            track_table = [x[0] for x in struct.iter_unpack('<L', f.read(640))]
            if track_table[0] == 688:
                track_table.extend([x[0] for x in
                                    struct.iter_unpack('<L', f.read(16))])
            elif track_table[0] != 672:
                raise error.Fatal("D88: Unsupported track table length.")

            d88 = cls(name)

            for track_index, track_offset in enumerate(track_table):
                if track_offset == 0:
                    continue
                f.seek(disk_offsets[index] + track_offset)
                if f.tell() >= disk_offsets[index] + disk_size:
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
                    error.check(status == 0x00,
                                'D88: FDC error codes are unsupported.')
                    error.check(deleted == 0x00,
                                'D88: Deleted data is unsupported.')
                    if track is None:
                        if media_flag == 0x00:

                            if mfm_flag == 0x40:
                                track = ibm.IBMTrack_FixedDef('ibm.fm')
                                track.rate = 125
                            else:
                                track = ibm.IBMTrack_FixedDef('ibm.mfm')
                                track.rate = 250
                            track.rpm = 300
                        else:
                            if mfm_flag == 0x40:
                                track = ibm.IBMTrack_FixedDef('ibm.fm')
                                track.rate = 250
                            else:
                                track = ibm.IBMTrack_FixedDef('ibm.mfm')
                                track.rate = 500
                            track.rpm = 360
                        track_mfm_flag = mfm_flag
                        num_sectors_track = num_sectors
                    error.check(mfm_flag == track_mfm_flag,
                                'D88: Mixed FM and MFM sectors in one track '
                                'are unsupported.')
                    error.check(num_sectors_track == num_sectors,
                                'D88: Corrupt number of sectors per track '
                                'in sector header.')
                    data = f.read(data_size)
                    size = 128 << n
                    error.check(size == data_size,
                                'D88: Extra sector data is unsupported.')
                    secs.append((c,h,r,n,data))
                if track is None:
                    continue
                track.secs = len(secs)
                track.sz = [x[3] for x in secs]
                track.finalise()
                t = ibm.IBMTrack_Fixed.from_config(
                    track, cyl, head, warn_on_oversize = False)

                # If the track is oversized, remove duplicate sectors, and
                # re-generate the track layout with oversize warning enabled.
                if t.oversized:
                    new_secs = d88.remove_duplicate_sectors(secs)
                    ndups = len(secs) - len(new_secs)
                    if ndups != 0:
                        print('T%d.%d: D88: Removed %d duplicate sectors '
                              'from oversized track' % (cyl, head, ndups))
                    secs = new_secs
                    track.secs = len(secs)
                    track.sz = [x[3] for x in secs]
                    t = ibm.IBMTrack_Fixed.from_config(
                        track, cyl, head, warn_on_oversize = True)

                for nr,s in enumerate(t.sectors):
                    c,h,r,n,data = secs[nr]
                    s.crc = s.idam.crc = s.dam.crc = 0
                    s.idam.c, s.idam.h, s.idam.r, s.idam.n = c,h,r,n
                    s.dam.data = data

                d88.to_track[cyl, head] = t

        return d88

    def get_track(self, cyl: int, side: int) -> Optional[ibm.IBMTrack_Fixed]:
        if (cyl,side) not in self.to_track:
            return None
        return self.to_track[cyl,side]

# Local variables:
# python-indent: 4
# End:
