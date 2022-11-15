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
from greaseweazle.codec.ibm import mfm, fm
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
            elif media_flag == 0x00:
                format_str = 'pc98.2d'
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
                if f.tell() >= disk_size:
                    continue
                if media_flag == 0x00:
                    physical_cyl = track_index // 2 * 2
                else:
                    physical_cyl = track_index // 2
                physical_head = track_index % 2
                track = None
                track_mfm_flag = None
                pos = None
                num_sectors_track = 255
                sector_idx = 0
                while sector_idx < num_sectors_track:
                    (c, h, r, n, num_sectors, mfm_flag, deleted, status, data_size) = \
                        struct.unpack('<BBBBHBBB5xH', f.read(16))
                    if status != 0x00:
                        raise error.Fatal('D88: FDC error codes are unsupported.')
                    if deleted != 0x00:
                        raise error.Fatal('D88: Deleted data is unsupported.')
                    if track is None:
                        if media_flag == 0x00:

                            if mfm_flag == 0x40:
                                track = fm.IBM_FM_Formatted(physical_cyl, physical_head)
                                track.clock = 4e-6
                                track.gap_3 = 0x1b
                            else:
                                track = mfm.IBM_MFM_Formatted(physical_cyl, physical_head)
                                track.clock = 2e-6
                                track.gap_3 = 0x1b
                            track.time_per_rev = 0.2
                        else:
                            if mfm_flag == 0x40:
                                track = fm.IBM_FM_Formatted(physical_cyl, physical_head)
                                track.clock = 2e-6
                                track.gap_3 = 0x1b
                            else:
                                track = mfm.IBM_MFM_Formatted(physical_cyl, physical_head)
                                track.clock = 1e-6
                                track.gap_3 = 116
                            track.time_per_rev = 60/360
                        pos = track.gap_4a
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
                    pos += track.gap_presync
                    if mfm_flag == 0x40:
                        idam = fm.IDAM(pos*16, (pos+7)*16, 0, c, h, r, n)
                        pos += 7 + track.gap_2 + track.gap_presync
                        dam = fm.DAM(pos*16, (pos+1+size+2)*16, 0, track.DAM, data)
                        sector = fm.Sector(idam, dam)
                        track.sectors.append(sector)
                        pos += 1 + size + 2 + track.gap_3
                    else:
                        idam = mfm.IDAM(pos*16, (pos+10)*16, 0, c, h, r, n)
                        pos += 10 + track.gap_2 + track.gap_presync
                        if size <= 128:
                            track.gap_3 = 0x1b
                        elif size <= 256:
                            track.gap_3 = 0x36
                        dam = mfm.DAM(pos*16, (pos+4+size+2)*16, 0, track.DAM, data)
                        sector = mfm.Sector(idam, dam)
                        track.sectors.append(sector)
                        pos += 4 + size + 2 + track.gap_3
                    sector_idx += 1

                img.to_track[physical_cyl, physical_head] = track

            img.format_str = format_str

        return img

# Local variables:
# python-indent: 4
# End:
