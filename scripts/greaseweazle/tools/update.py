# greaseweazle/tools/update.py
#
# Greaseweazle control script: Firmware Update.
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import sys, argparse, serial, struct, os
import crcmod.predefined

from greaseweazle.tools import util
from greaseweazle import version
from greaseweazle import usb as USB

# update_firmware:
# Updates the Greaseweazle firmware using the specified Update File.
def update_firmware(usb, args):

    filename = args.file
    if filename == "auto":
        # Get the absolute path to the root Greaseweazle folder.
        path = os.path.dirname(os.path.abspath(__file__))
        for _ in range(3):
            path = os.path.join(path, os.pardir)
        path = os.path.normpath(path)
        filename = os.path.join(path, "Greaseweazle-v%d.%d.upd"
                                % (version.major, version.minor))
    
    # Read the entire update catalogue.
    with open(filename, "rb") as f:
        dat = f.read()

    # Search the catalogue for a match on our Weazle's hardware type.
    while dat:
        upd_len, hw_type = struct.unpack("<2H", dat[:4])
        if hw_type == usb.hw_type:
            # Match: Pull out the embedded update file.
            dat = dat[4:upd_len+4]
            break
        # Skip to the next catalogue entry.
        dat = dat[upd_len+4:]

    if not dat:
        print("%s: No match for hardware type %x" % (filename, usb.hw_type))
        return

    # Check the matching update file's footer.
    sig, maj, min, hw_type = struct.unpack("<2s2BH", dat[-8:-2])
    if len(dat) & 3 != 0 or sig != b'GW' or hw_type != usb.hw_type:
        print("%s: Bad update file" % (filename))
        return
    crc16 = crcmod.predefined.Crc('crc-ccitt-false')
    crc16.update(dat)
    if crc16.crcValue != 0:
        print("%s: Bad CRC" % (filename))
        return

    # Perform the update.
    print("Updating to v%u.%u..." % (maj, min))
    ack = usb.update_firmware(dat)
    if ack != 0:
        print("** UPDATE FAILED: Please retry!")
        return
    print("Done.")
    
    if usb.hw_type == 7:
        util.usb_reopen(usb, is_update=False)
    else:
        print("** Disconnect Greaseweazle and remove the Programming Jumper.")


def main(argv):

    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("file", nargs="?", default="auto",
                        help="update filename")
    parser.add_argument("device", nargs="?", default="auto",
                        help="serial device")
    parser.prog += ' ' + argv[1]
    args = parser.parse_args(argv[2:])

    usb = util.usb_open(args.device, is_update=True)

    try:
        update_firmware(usb, args)
    except USB.CmdError as error:
        print("Command Failed: %s" % error)


if __name__ == "__main__":
    main(sys.argv)

# Local variables:
# python-indent: 4
# End:
