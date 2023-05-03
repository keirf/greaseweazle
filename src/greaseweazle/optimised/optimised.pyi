# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from typing import Any, List, Tuple, Union

def flux_to_bitcells(bit_array, time_array, revolutions,
                     index_iter, flux_iter,
                     freq, clock_centre, clock_min, clock_max,
                     pll_period_adj, pll_phase_adj) -> None:
    ...

def decode_flux(dat: bytes) -> Tuple[List[float], List[float]]:
    ...
    
# Local variables:
# python-indent: 4
# End:
