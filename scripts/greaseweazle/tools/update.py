# greaseweazle/tools/update.py
#
# Greaseweazle control script: Firmware Update.
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

description = "Update the Greaseweazle device firmware to current version."

import sys, serial, struct, os
import crcmod.predefined

from greaseweazle.tools import util
from greaseweazle import version
from greaseweazle import usb as USB

# update_firmware:
# Updates the Greaseweazle firmware using the specified Update File.
def update_firmware(usb, args):

    req_type = b'BL' if args.bootloader else b'GW'

    filename = args.file
    if filename is None:
        # Get the absolute path to the root Greaseweazle folder.
        path = os.path.dirname(os.path.abspath(__file__))
        for _ in range(3):
            path = os.path.join(path, os.pardir)
        path = os.path.normpath(path)
        filename = os.path.join(path, "Greaseweazle-v%d.%d.upd"
                                % (version.major, version.minor))
    
    # Read and verify the entire update catalogue.
    with open(filename, "rb") as f:
        dat = f.read()
    if struct.unpack('4s', dat[:4])[0] != b'GWUP':
        print('%s: Not a valid UPD file' % (filename))
        return
    crc32 = crcmod.predefined.Crc('crc-32-mpeg')
    crc32.update(dat)
    if crc32.crcValue != 0:
        print('%s: UPD file is corrupt' % (filename))
        return
    dat = dat[4:-4]

    # Search the catalogue for a match on our Weazle's hardware type.
    while dat:
        upd_len, hw_model = struct.unpack("<2H", dat[:4])
        upd_type, major, minor = struct.unpack("2s2B", dat[upd_len-4:upd_len])
        if ((hw_model, upd_type, major, minor)
            == (usb.hw_model, req_type, version.major, version.minor)):
            # Match: Pull out the embedded update file.
            dat = dat[4:upd_len+4]
            break
        # Skip to the next catalogue entry.
        dat = dat[upd_len+4:]

    if not dat:
        print("%s: F%u v%u.%u %s update not found"
              % (filename, usb.hw_model,
                 version.major, version.minor,
                 'bootloader' if args.bootloader else 'firmware'))
        return

    # Check the matching update file's footer.
    sig, maj, min, hw_model = struct.unpack("<2s2BH", dat[-8:-2])
    if len(dat) & 3 != 0 or sig != req_type or hw_model != usb.hw_model:
        print("%s: Bad update file" % (filename))
        return
    crc16 = crcmod.predefined.Crc('crc-ccitt-false')
    crc16.update(dat)
    if crc16.crcValue != 0:
        print("%s: Bad CRC" % (filename))
        return

    # Perform the update.
    print("Updating %s to v%u.%u..."
          % ("Bootloader" if args.bootloader else "Main Firmware", maj, min))
    if args.bootloader:
        ack = usb.update_bootloader(dat)
        if ack != 0:
            print("""\
** UPDATE FAILED: Please retry immediately or your Weazle may need
        full reflashing via a suitable programming adapter!""")
            return
        print("Done.")
    else:
        ack = usb.update_firmware(dat)
        if ack != 0:
            print("** UPDATE FAILED: Please retry!")
            return
        print("Done.")
    
        if usb.jumperless_update:
            util.usb_reopen(usb, is_update=False)
        else:
            print("** Disconnect Greaseweazle and remove the Update Jumper")


def main(argv):

    parser = util.ArgumentParser(allow_abbrev=False, usage='%(prog)s [options] [file]')
    parser.add_argument("file", nargs="?", help="update filename")
    parser.add_argument("--device", help="greaseweazle device name")
    parser.add_argument("--bootloader", action="store_true",
                        help="update the bootloader (use with caution!)")
    parser.description = description
    parser.prog += ' ' + argv[1]
    args = parser.parse_args(argv[2:])

    try:
        usb = util.usb_open(args.device, is_update=not args.bootloader)
        update_firmware(usb, args)
    except USB.CmdError as error:
        if error.code == USB.Ack.OutOfSRAM and args.bootloader:
            # Special warning for Low-Density F1 devices. The new bootloader
            # cannot be fully buffered in the limited RAM available.
            print("ERROR: Bootloader update unsupported on this device "
                  "(insufficient SRAM)")
        elif error.code == USB.Ack.OutOfFlash and not args.bootloader:
            print("ERROR: New firmware is too large for this device "
                  "(insufficient Flash memory)")
        else:
            print("Command Failed: %s" % error)


if __name__ == "__main__":
    main(sys.argv)

# Local variables:
# python-indent: 4
# End:
