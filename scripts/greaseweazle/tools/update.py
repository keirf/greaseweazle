# greaseweazle/tools/update.py
#
# Greaseweazle control script: Firmware Update.
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

import sys, argparse
import crcmod.predefined

from greaseweazle.tools import util
from greaseweazle import usb as USB

# update_firmware:
# Updates the Greaseweazle firmware using the specified Update File.
def update_firmware(usb, args):

    # Read and check the update file.
    with open(args.file, "rb") as f:
        dat = f.read()
    sig, maj, min, pad1, pad2, crc = struct.unpack(">2s4BH", dat[-8:])
    if len(dat) & 3 != 0 or sig != b'GW' or pad1 != 0 or pad2 != 0:
        print("%s: Bad update file" % (args.file))
        return
    crc16 = crcmod.predefined.Crc('crc-ccitt-false')
    crc16.update(dat)
    if crc16.crcValue != 0:
        print("%s: Bad CRC" % (args.file))

    # Perform the update.
    print("Updating to v%u.%u..." % (maj, min))
    ack = usb.update_firmware(dat)
    if ack != 0:
        print("** UPDATE FAILED: Please retry!")
        return
    print("Done.")
    print("** Disconnect Greaseweazle and remove the Programming Jumper.")


def main(argv):

    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("file", help="update filename")
    parser.add_argument("device", help="serial device")
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
