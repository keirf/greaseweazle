# greaseweazle/tools/align.py
#
# Greaseweazle control script: Repeatedly read the same track for alignment.
#
# Released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

from enum import Enum

from greaseweazle import error
from greaseweazle.codec import codec
from greaseweazle.image.img import IMG


class Apridisk(IMG):

    def from_bytes(self, dat: bytes) -> None:
        error.check(len(dat) >= 128, "Apridisk file missing 129 byte header")
        dat = dat[128:]

        records = ApridiskRecord.split_apridisk_file(dat, self.fmt)
        records.sort(key = lambda h : h.ord)

        data = bytes([i for r in records for i in r.expand_record()])
        super().from_bytes(data)

class ApridiskRecord:
    def __init__(self, data: bytes, fmt: codec.DiskDef):
        error.check(len(data) >= 16, "Apridisk record contains no header")
        
        self.fmt = fmt
        self.itm_type = ApridiskSecType.from_bytes(data[:4])
        self.header_size = int.from_bytes(data[6:8], byteorder="little")
        self.data_size = int.from_bytes(data[8:12], byteorder="little")
        
        self.record_size = self.header_size + self.data_size
        error.check(len(data) >= self.record_size, 
                    f"Apridisk file ends before end of record. ")
        self.data = data[self.header_size : self.record_size]

        self._match_pos(data)
        self._match_compression(data)

    @staticmethod
    def split_apridisk_file(file: bytes, fmt: codec.DiskDef) -> list[ApridiskRecord]:
        res: list[ApridiskRecord] = []
        byte = 0
        while file:
            record = ApridiskRecord(file, fmt)
            res.append(record)
            byte += record.record_size
            file = file[record.record_size:]
        return res

    def expand_record(self) -> bytes:
        if self.itm_type != ApridiskSecType.SECTOR:
            return b''
        if self.compression:
            return bytes([self.byte for _ in range(0, self.count)])
        return self.data

    def _match_compression(self, data: bytes):
        compression = int.from_bytes(data[4:6], byteorder="little")
        error.check(compression in [0x9E90, 0x3E5A],
                    f"Apridisk unknown compression scheme: {compression}")
        self.compression = compression == 0x3E5A

        if self.compression:
            error.check(len(self.data) == 3, 
                        f"Apridisk compressed section length must be 3, length: {len(self.data)}")
            self.count = int.from_bytes(self.data[0:2], byteorder="little")
            self.byte = self.data[2]

    def _match_pos(self, data: bytes):
        error.check(data[12] in range(0, self.fmt.heads or 2),
                    f"Apridisk heads out of range (max {self.fmt.heads or 2}): {hex(data[12])}")
        self.head = data[12]

        error.check(data[13] in range(1, 19) or self.itm_type != ApridiskSecType.SECTOR,
                    f"Apridisk sector out of range (must be 1-9): {data[13]}")
        self.sector = data[13]

        cyl = int.from_bytes(data[14:16], byteorder="little")
        error.check(cyl in range(0, self.fmt.cyls or 80),
                    f"Apridisk cylinder out of range for chosen format (max {self.fmt.cyls}): {cyl}")
        self.cyl = cyl

        # Used for sorting
        self.ord = self.sector + (self.head * 20) + (self.cyl * 100)

class ApridiskSecType(Enum):
    DELETED = 0xE31D0000
    SECTOR = 0xE31D0001
    COMMENT = 0xE31D0002
    CREATOR = 0xE31D0003

    @staticmethod
    def from_bytes(b: bytes) -> ApridiskSecType:
        num = int.from_bytes(b[:4], byteorder="little")
        try:
            return ApridiskSecType(num)
        except:
            raise error.Fatal(f"Unknown Apridisk sector type: {hex(num)}")

# Local variables:
# python-indent: 4
# End:
