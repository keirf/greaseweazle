# ipf_align.py
# 
# Align all tracks in an IPF image to the same offset from index mark.
# 
# Written & released by Keir Fraser <keir.xen@gmail.com>
# 
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import struct, sys, crcmod.predefined

def main(argv):
    crc32 = crcmod.predefined.Crc('crc-32')
    offset = 1024
    if len(argv) == 4:
        offset = int(argv[3])
    elif len(argv) != 3:
        print("%s <input_file> <output_file> [<offset>]" % argv[0])
        return
    with open(argv[1], "rb") as f:
        in_dat = bytearray(f.read())
    out_dat = bytearray()
    while in_dat:
        # Decode the common record header
        id, length, crc = struct.unpack(">4s2I", in_dat[:12])
        # Consume the record from the input array
        record = in_dat[:length]
        in_dat = in_dat[length:]
        # Check the CRC
        record[8:12] = bytes(4)
        assert crc == crc32.new(record).crcValue, "CRC mismatch"
        # Modify the record as necessary
        if id == b'IMGE':
            trkbits, = struct.unpack(">I", record[48:52])
            if trkbits > offset:
                record[32:40] = struct.pack(">2I", offset//8, offset)
        # Re-calculate the CRC
        record[8:12] = struct.pack(">I", crc32.new(record).crcValue)
        # DATA chunk has extra data to copy
        if id == b'DATA':
            size, bsize, dcrc, datchunk = struct.unpack(">4I", record[12:28])
            record += in_dat[:size]
            in_dat = in_dat[size:]
        # Write the full modified record into the output array
        out_dat += record
    with open(argv[2], "wb") as f:
        f.write(out_dat)
    
if __name__ == "__main__":
    main(sys.argv)
