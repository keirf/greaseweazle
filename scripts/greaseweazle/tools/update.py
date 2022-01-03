# greaseweazle/tools/update.py
#
# Greaseweazle control script: Firmware Update.
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

description = "Update the Greaseweazle device firmware to current version."

import requests, zipfile, io, re
import sys, serial, struct, os
import crcmod.predefined

from greaseweazle.tools import util
from greaseweazle import error
from greaseweazle import version
from greaseweazle import usb as USB

def update_firmware(usb, dat, args):
    '''Updates the Greaseweazle firmware using the specified Update File.'''

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
    
        if not usb.jumperless_update:
            print("** Disconnect Greaseweazle and remove the Update Jumper")


def extract_update(usb, dat, args):

    req_type = b'BL' if args.bootloader else b'GW'

    filename = args.file

    # Verify the update catalogue.
    error.check(struct.unpack('4s', dat[:4])[0] == b'GWUP',
                '%s: Not a valid UPD file' % (filename))
    crc32 = crcmod.predefined.Crc('crc-32-mpeg')
    crc32.update(dat)
    error.check(crc32.crcValue == 0,
                '%s: UPD file is corrupt' % (filename))
    dat = dat[4:-4]

    # Search the catalogue for a match on our Weazle's hardware type.
    while dat:
        upd_len, hw_model = struct.unpack("<2H", dat[:4])
        upd_type, major, minor = struct.unpack("2s2B", dat[upd_len-4:upd_len])
        if ((hw_model, upd_type) == (usb.hw_model, req_type)):
            # Match: Pull out the embedded update file.
            dat = dat[4:upd_len+4]
            break
        # Skip to the next catalogue entry.
        dat = dat[upd_len+4:]

    error.check(dat, '%s: F%u %s update not found'
                % (filename, usb.hw_model,
                   'bootloader' if args.bootloader else 'firmware'))

    # Check the matching update file's footer.
    sig, major, minor, hw_model = struct.unpack("<2s2BH", dat[-8:-2])
    error.check(len(dat) & 3 == 0 and sig == req_type
                and hw_model == usb.hw_model,
                '%s: Bad update file' % (filename))
    crc16 = crcmod.predefined.Crc('crc-ccitt-false')
    crc16.update(dat)
    error.check(crc16.crcValue == 0, '%s: Bad CRC' % (filename))

    return (major, minor), dat


def download_latest():
    '''Download the latest Update File from GitHub.'''
    rsp = requests.get('https://api.github.com/repos/keirf/'
                       'greaseweazle-firmware/releases/latest', timeout=5)
    tag = rsp.json()['tag_name']
    r = re.match(r'v(\d+)\.(\d+)', tag)
    major, minor = r.group(1), r.group(2)
    name = 'greaseweazle-firmware-'+tag+'.upd'
    print('Downloading latest firmware: '+name)
    rsp = requests.get('https://github.com/keirf/greaseweazle-firmware'
                       '/releases/download/'+tag+
                       '/greaseweazle-firmware-'+tag+'.zip',
                       timeout=10)
    z = zipfile.ZipFile(io.BytesIO(rsp._content))
    return name, z.read('greaseweazle-firmware-'+tag+'/'+name)


def main(argv):

    parser = util.ArgumentParser(allow_abbrev=False, usage='%(prog)s [options] [file]')
    parser.add_argument("file", nargs="?", help="update filename")
    parser.add_argument("--device", help="device name (COM/serial port)")
    parser.add_argument("--force", action="store_true",
                        help="force update even if firmware is older")
    parser.add_argument("--bootloader", action="store_true",
                        help="update the bootloader (use with caution!)")
    parser.description = description
    parser.prog += ' ' + argv[1]
    args = parser.parse_args(argv[2:])

    if args.file is None:
        args.file, dat = download_latest()
    else:
        with open(args.file, "rb") as f:
            dat = f.read()

    try:
        usb = util.usb_open(args.device, mode_check=False)
        dat_version, dat = extract_update(usb, dat, args)
        print("Updating %s to v%u.%u..."
              % ("Bootloader" if args.bootloader else "Main Firmware",
                 *dat_version))
        if not args.force and (usb.can_mode_switch
                               or args.bootloader == usb.update_mode):
            if args.bootloader != usb.update_mode:
                usb = util.usb_reopen(usb, is_update=args.bootloader)
                error.check(args.bootloader == usb.update_mode,
                            'Device did not mode switch as requested')
            if usb.version >= dat_version:
                if usb.update_mode and usb.can_mode_switch:
                    usb = util.usb_reopen(usb, is_update=False)
                raise error.Fatal('Device is running v%d.%d (>= v%d.%d). '
                                  'Use --force to update anyway.'
                                  % (usb.version + dat_version))
        usb = util.usb_mode_check(usb, is_update=not args.bootloader)
        update_firmware(usb, dat, args)
        if usb.update_mode and usb.can_mode_switch:
            util.usb_reopen(usb, is_update=False)
    except USB.CmdError as err:
        if err.code == USB.Ack.OutOfSRAM and args.bootloader:
            # Special warning for Low-Density F1 devices. The new bootloader
            # cannot be fully buffered in the limited RAM available.
            print("ERROR: Bootloader update unsupported on this device "
                  "(insufficient SRAM)")
        elif err.code == USB.Ack.OutOfFlash and not args.bootloader:
            print("ERROR: New firmware is too large for this device "
                  "(insufficient Flash memory)")
        else:
            print("Command Failed: %s" % err)


if __name__ == "__main__":
    main(sys.argv)

# Local variables:
# python-indent: 4
# End:
