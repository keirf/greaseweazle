# greaseweazle/image/d88.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import struct
import os

from greaseweazle import error
from greaseweazle.image.img import IMG
from greaseweazle.codec.formats import *
from greaseweazle.codec.ibm import mfm
from .image import Image

from greaseweazle.codec import formats

class D88(IMG):
    default_format = None
    read_only = True

    @classmethod
    def from_file(cls, name, fmt=None):

        with open(name, "rb") as f:
            header = f.read(32)
            (disk_name, terminator, write_protect, media_flag, disk_size) = struct.unpack('<16sB9xBBL', header)
            if media_flag == 0x20:
                format_str = 'pc98.hd'
            else:
                raise error.Fatal("D88: Unsupported media format.")
            fmt = formats.formats[format_str]()
            track_table = [x[0] for x in struct.iter_unpack('<L', f.read(640))]
            if track_table[0] == 688:
                track_table.extend([x[0] for x in struct.iter_unpack('<L', f.read(16))])
            elif track_table[0] != 672:
                raise error.Fatal("D88: Unsupported track table length.")
            f.seek(0, os.SEEK_END)
            if f.tell() != disk_size:
                print('D88: Warning: Multiple disks found in image, only using first.')

            img = cls(name, fmt)

            for track_index, track_offset in enumerate(track_table):
                if track_offset == 0:
                    continue
                f.seek(track_offset)
                if track_index == len(track_table) - 1:
                    track_end = disk_size
                else:
                    track_end = track_table[track_index + 1]
                f.seek(track_offset)
                physical_cyl = track_index // 2
                physical_head = track_index % 2
                track = mfm.IBM_MFM_Formatted(physical_cyl, physical_head)
                track.time_per_rev = 60/360
                track.clock = 1e-6
                track.gap_3 = 116
                pos = track.gap_4a
                while f.tell() < track_end:
                    (c, h, r, n, num_sectors, fm, deleted, status, data_size) = \
                        struct.unpack('<BBBBHBBB5xH', f.read(16))
                    if fm == 0x40:
                        raise error.Fatal('D88: FM encoded sectors are unsupported.')
                    if status != 0x00:
                        raise error.Fatal('D88: FDC error codes are unsupported.')
                    if deleted != 0x00:
                        raise error.Fatal('D88: Deleted data is unsupported.')
                    data = f.read(data_size)
                    pos += track.gap_presync
                    idam = mfm.IDAM(pos*16, (pos+10)*16, 0, c, h, r, n)
                    pos += 10 + track.gap_2 + track.gap_presync
                    size = 128 << n
                    if size != data_size:
                        raise error.Fatal('D88: Extra sector data is unsupported.')
                    dam = mfm.DAM(pos*16, (pos+4+size+2)*16, 0, track.DAM, data)
                    sector = mfm.Sector(idam, dam)
                    track.sectors.append(sector)
                    pos += 4 + size + 2 + track.gap_3

                img.to_track[physical_cyl, physical_head] = track

            img.format_str = format_str

        return img

# Local variables:
# python-indent: 4
# End:
