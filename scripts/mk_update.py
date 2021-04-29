# mk_update.py new <output> <bootloader> <main_firmware> <stm_model>
# mk_update.py cat <output> <update_file>*
# mk_update.py verify <update_file>*
#
# Convert a raw firmware binary into an update file for our bootloader.
#
# Update Format (Little endian, unless otherwise stated):
#   File Header:
#     4 bytes: 'GWUP'
#   Catalogue Header:
#     2 bytes: <length> (excludes Catalogue Header)
#     2 bytes: <hw_model>
#   Payload:
#     N bytes: <raw binary data>
#   Footer:
#     2 bytes: 'GW' or 'BL'
#     2 bytes: major, minor
#     2 bytes: <hw_model>
#     2 bytes: CRC16-CCITT, seed 0xFFFF (big endian, excludes Catalogue Header)
#   File Footer:
#     4 bytes: CRC32 (MPEG-2, big endian)
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import crcmod.predefined
import re, struct, sys

from greaseweazle import version

name_to_hw_model = { 'stm32f1': 1,
                     'stm32f7': 7,
                     'at32f415': 4 }

hw_model_to_name = { 1: 'STM32F103',
                     7: 'STM32F730',
                     4: 'AT32F415' }

def mk_cat_entry(dat, hw_model, sig):
    max_kb = { 1: { b'BL':  8, b'GW': 56 },
               7: { b'BL': 16, b'GW': 48 },
               4: { b'BL': 16, b'GW': 48 } }
    dlen = len(dat)
    assert (dlen & 3) == 0, "input is not longword padded"
    assert dlen <= max_kb[hw_model][sig]*1024, "input is too long"
    header = struct.pack("<2H", dlen + 8, hw_model)
    footer = struct.pack("<2s2BH", sig, version.major, version.minor, hw_model)
    crc16 = crcmod.predefined.Crc('crc-ccitt-false')
    crc16.update(dat)
    crc16.update(footer)
    footer += struct.pack(">H", crc16.crcValue)
    return header + dat + footer

def new_upd(argv):
    dat = b'GWUP'
    hw_model = name_to_hw_model[argv[2]]
    with open(argv[1], "rb") as gw_f:
        dat += mk_cat_entry(gw_f.read(), hw_model, b'GW')
    with open(argv[0], "rb") as bl_f:
        dat += mk_cat_entry(bl_f.read(), hw_model, b'BL')
    return dat

def cat_upd(argv):
    dat = b'GWUP'
    for fname in argv:
        with open(fname, "rb") as f:
            d = f.read()
        assert struct.unpack('4s', d[:4])[0] == b'GWUP'
        crc32 = crcmod.predefined.Crc('crc-32-mpeg')
        crc32.update(d)
        assert crc32.crcValue == 0
        dat += d[4:-4]
    return dat

def _verify_upd(d):
    assert struct.unpack('4s', d[:4])[0] == b'GWUP'
    crc32 = crcmod.predefined.Crc('crc-32-mpeg')
    crc32.update(d)
    assert crc32.crcValue == 0
    d = d[4:-4]
    while d:
        upd_len, hw_model = struct.unpack("<2H", d[:4])
        upd_type, major, minor = struct.unpack("2s2B", d[upd_len-4:upd_len])
        crc16 = crcmod.predefined.Crc('crc-ccitt-false')
        crc16.update(d[4:upd_len+4])
        assert crc16.crcValue == 0
        print('%s %s v%u.%u: %u bytes'
              % (hw_model_to_name[hw_model],
                 {b'BL': 'Boot', b'GW': 'Main'}[upd_type],
                 major, minor, upd_len))
        d = d[upd_len+4:]

def verify_upd(argv):
    for fname in argv:
        with open(fname, "rb") as f:
            d = f.read()
        _verify_upd(d)
    
def main(argv):
    if argv[1] == 'new':
        dat = new_upd(argv[3:])
    elif argv[1] == 'cat':
        dat = cat_upd(argv[3:])
    elif argv[1] == 'verify':
        verify_upd(argv[2:])
        return
    else:
        assert False
    crc32 = crcmod.predefined.Crc('crc-32-mpeg')
    crc32.update(dat)
    dat += struct.pack(">I", crc32.crcValue)
    with open(argv[2], "wb") as out_f:
        out_f.write(dat)

if __name__ == "__main__":
    main(sys.argv)

# Local variables:
# python-indent: 4
# End:
