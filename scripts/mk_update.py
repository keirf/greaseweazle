# mk_update.py
#
# Convert a raw firmware binary into an update file for our bootloader.
#
# Update Format (Little endian, unless otherwise stated):
#   Catalogue Header:
#     2 bytes: <length> (excludes Catalogue Header)
#     2 bytes: <hw_type>
#   Payload:
#     N bytes: <raw binary data>
#   Footer:
#     2 bytes: 'GW'
#     2 bytes: major, minor
#     2 bytes: <hw_type>
#     2 bytes: CRC16-CCITT, seed 0xFFFF (big endian, excludes Catalogue Header)
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import crcmod.predefined
import re, struct, sys

from greaseweazle import version

def main(argv):
    in_f = open(argv[1], "rb")
    out_f = open(argv[2], "wb")
    hw_type = int(re.match("f(\d)", argv[3]).group(1))
    in_dat = in_f.read()
    in_len = len(in_dat)
    assert (in_len & 3) == 0, "input is not longword padded"
    crc16 = crcmod.predefined.Crc('crc-ccitt-false')
    out_f.write(struct.pack("<2H", in_len + 8, hw_type))
    out_f.write(in_dat)
    crc16.update(in_dat)
    in_dat = struct.pack("<2s2BH", b'GW', version.major, version.minor, hw_type)
    out_f.write(in_dat)
    crc16.update(in_dat)
    in_dat = struct.pack(">H", crc16.crcValue)
    out_f.write(in_dat)

if __name__ == "__main__":
    main(sys.argv)

# Local variables:
# python-indent: 4
# End:
