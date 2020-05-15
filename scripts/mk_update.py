# mk_update.py <bootloader> <main_firmware> <output> <stm_type>
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
#     2 bytes: 'GW' or 'BL'
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

def mk_cat_entry(dat, hw_type, sig):
    max_kb = { 1: { b'BL':  8, b'GW': 56 },
               7: { b'BL': 16, b'GW': 48 } }
    dlen = len(dat)
    assert (dlen & 3) == 0, "input is not longword padded"
    assert dlen <= max_kb[hw_type][sig]*1024, "input is too long"
    header = struct.pack("<2H", dlen + 8, hw_type)
    footer = struct.pack("<2s2BH", sig, version.major, version.minor, hw_type)
    crc16 = crcmod.predefined.Crc('crc-ccitt-false')
    crc16.update(dat)
    crc16.update(footer)
    footer += struct.pack(">H", crc16.crcValue)
    return header + dat + footer

def main(argv):
    out_f = open(argv[3], "wb")
    hw_type = int(re.match("f(\d)", argv[4]).group(1))
    with open(argv[2], "rb") as gw_f:
        out_f.write(mk_cat_entry(gw_f.read(), hw_type, b'GW'))
    with open(argv[1], "rb") as bl_f:
        out_f.write(mk_cat_entry(bl_f.read(), hw_type, b'BL'))

if __name__ == "__main__":
    main(sys.argv)

# Local variables:
# python-indent: 4
# End:
