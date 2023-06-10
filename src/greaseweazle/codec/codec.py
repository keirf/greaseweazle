# greaseweazle/codec/codec.py
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from typing import Optional

from abc import abstractmethod

from greaseweazle.track import PLL, MasterTrack
from greaseweazle.flux import Flux

class Codec:

    @property
    @abstractmethod
    def nsec(self) -> int:
        ...

    @abstractmethod
    def summary_string(self) -> str:
        ...

    @abstractmethod
    def has_sec(self, sec_id: int) -> bool:
        ...

    @abstractmethod
    def nr_missing(self) -> int:
        ...

    @abstractmethod
    def get_img_track(self) -> bytearray:
        ...

    @abstractmethod
    def set_img_track(self, tdat: bytearray) -> int:
        ...

    @abstractmethod
    def decode_raw(self, track, pll: Optional[PLL]) -> None:
        ...

    @abstractmethod
    def master_track(self) -> MasterTrack:
        ...

    def flux(self) -> Flux:
        return self.master_track().flux()

# Local variables:
# python-indent: 4
# End:
