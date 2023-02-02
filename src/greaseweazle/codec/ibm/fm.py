# greaseweazle/codec/ibm/fm.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .ibm import IBMTrackFormat

from .ibm import IBMTrackFormatted
from .ibm import IAM, IDAM, DAM, Sector, Mark, Mode

class IBM_FM_Formatted(IBMTrackFormatted):

    GAP_1  = 26 # Post-IAM
    GAP_2  = 11 # Post-IDAM
    GAP_3  = [ 27, 42, 58, 138, 255, 255, 255, 255 ]

    def __init__(cls, cyl: int, head: int):
        super().__init__(cyl, head, Mode.FM)
    
    @classmethod
    def from_config(cls, config: IBMTrackFormat, cyl: int, head: int):

        def sec_n(i):
            return config.sz[i] if i < len(config.sz) else config.sz[-1]

        t = cls(cyl, head)
        t.nsec = nsec = config.secs
        t.img_bps = config.img_bps

        if config.iam:
            gap_1 = t.GAP_1 if config.gap1 is None else config.gap1
        else:
            gap_1 = None
        gap_2 = t.GAP_2 if config.gap2 is None else config.gap2
        gap_3 = 0 if config.gap3 is None else config.gap3
        if config.gap4a is None:
            gap_4a = 40 if config.iam else 16
        else:
            gap_4a = config.gap4a

        idx_sz = gap_4a
        if gap_1 is not None:
            idx_sz += t.gap_presync + 1 + gap_1
        idam_sz = t.gap_presync + 5 + 2 + gap_2
        dam_sz_pre = t.gap_presync + 1
        dam_sz_post = 2 + gap_3

        tracklen = idx_sz + (idam_sz + dam_sz_pre + dam_sz_post) * nsec
        for i in range(nsec):
            tracklen += 128 << sec_n(i)
        tracklen *= 16

        rate, rpm = config.rate, config.rpm
        if rate == 0:
            # Micro-diskette = 125kbps, 8-inch disk = 250kbps
            for i in range(2): # 0=125kbps, 1=250kbps
                maxlen = ((50000*300//rpm) << i) + 5000
                if tracklen < maxlen:
                    break
            rate = 125 << i # 125kbps or 250kbps

        tracklen_bc = rate * 400 * 300 // rpm

        if nsec != 0 and config.gap3 is None:
            space = max(0, tracklen_bc - tracklen)
            no = sec_n(0)
            gap_3 = min(space // (16*nsec), t.GAP_3[no])
            dam_sz_post += gap_3
            tracklen += 16 * nsec * gap_3

        tracklen_bc = max(tracklen_bc, tracklen)

        t.time_per_rev = 60 / rpm
        t.clock = t.time_per_rev / tracklen_bc

        # Create logical sector map in rotational order
        sec_map, pos = [-1] * nsec, 0
        if nsec != 0:
            pos = (cyl*config.cskew + head*config.hskew) % nsec
        for i in range(nsec):
            while sec_map[pos] != -1:
                pos = (pos + 1) % nsec
            sec_map[pos] = i
            pos = (pos + config.interleave) % nsec

        pos = gap_4a
        if gap_1 is not None:
            pos += t.gap_presync
            t.iams = [IAM(pos*16,(pos+1)*16)]
            pos += 1 + gap_1

        id0 = config.id
        h = head if config.h is None else config.h
        for i in range(nsec):
            sec = sec_map[i]
            pos += t.gap_presync
            idam = IDAM(pos*16, (pos+7)*16, 0xffff,
                        c = cyl, h = h, r= id0+sec, n = sec_n(sec))
            pos += 7 + gap_2 + t.gap_presync
            size = 128 << idam.n
            dam = DAM(pos*16, (pos+1+size+2)*16, 0xffff,
                      mark=Mark.DAM, data=b'-=[BAD SECTOR]=-'*(size//16))
            t.sectors.append(Sector(idam, dam))
            pos += 1 + size + 2 + gap_3

        return t




# Local variables:
# python-indent: 4
# End:
