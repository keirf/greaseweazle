# greaseweazle/codec/ibm/mfm.py
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

class IBM_MFM_Formatted(IBMTrackFormatted):

    GAP_4A = 80 # Post-Index
    GAP_1  = 50 # Post-IAM
    GAP_2  = 22 # Post-IDAM
    GAP_3  = [ 32, 54, 84, 116, 255, 255, 255, 255 ]

    def __init__(cls, cyl: int, head: int):
        super().__init__(cyl, head, Mode.MFM)
    
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
        gap_4a = t.GAP_4A if config.gap4a is None else config.gap4a

        idx_sz = gap_4a
        if gap_1 is not None:
            idx_sz += t.gap_presync + 4 + gap_1
        idam_sz = t.gap_presync + 8 + 2 + gap_2
        dam_sz_pre = t.gap_presync + 4
        dam_sz_post = 2 + gap_3

        tracklen = idx_sz + (idam_sz + dam_sz_pre + dam_sz_post) * nsec
        for i in range(nsec):
            tracklen += 128 << sec_n(i)
        tracklen *= 16

        rate, rpm = config.rate, config.rpm
        if rate == 0:
            for i in range(1, 4): # DD=1, HD=2, ED=3
                maxlen = ((50000*300//rpm) << i) + 5000
                if tracklen < maxlen:
                    break
            rate = 125 << i # DD=250, HD=500, ED=1000

        if config.gap2 is None and rate >= 1000:
            # At ED rate the default GAP2 is 41 bytes.
            old_gap_2 = gap_2
            gap_2 = 41
            idam_sz += gap_2 - old_gap_2
            tracklen += 16 * nsec * (gap_2 - old_gap_2)
            
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
            t.iams = [IAM(pos*16,(pos+4)*16)]
            pos += 4 + gap_1

        id0 = config.id
        h = head if config.h is None else config.h
        for i in range(nsec):
            sec = sec_map[i]
            pos += t.gap_presync
            idam = IDAM(pos*16, (pos+10)*16, 0xffff,
                        c = cyl, h = h, r = id0+sec, n = sec_n(sec))
            pos += 10 + gap_2 + t.gap_presync
            size = 128 << idam.n
            dam = DAM(pos*16, (pos+4+size+2)*16, 0xffff,
                      mark=Mark.DAM, data=b'-=[BAD SECTOR]=-'*(size//16))
            t.sectors.append(Sector(idam, dam))
            pos += 4 + size + 2 + gap_3

        return t




# Local variables:
# python-indent: 4
# End:
