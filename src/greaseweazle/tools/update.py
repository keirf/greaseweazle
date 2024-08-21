# greaseweazle/tools/update.py
#
# Greaseweazle control script: Firmware Update.
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

description = ("Update the Greaseweazle device firmware to latest "
               "(or specified) version.")

import requests, zipfile, io, re
import sys, serial, struct, os, textwrap
import crcmod.predefined

from greaseweazle.tools import util
from greaseweazle import error
from greaseweazle import usb as USB

class SkipUpdate(Exception):
    pass

def update_firmware(usb, dat, args):
    '''Updates the device firmware using the specified Update File.'''

    if args.bootloader:
        ack = usb.update_bootloader(dat)
        if ack != 0:
            print("""\
** UPDATE FAILED: Please retry immediately or your Weazle may need
        full reflashing via a suitable programming adapter!""")
            return
        print("Done.")
    else:
        ack = usb.update_main_firmware(dat)
        if ack != 0:
            print("** UPDATE FAILED: Please retry!")
            return
        print("Done.")
    
        if not usb.jumperless_update:
            print("** Unplug device and remove the Update Jumper")


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

def gh_request_get(url, timeout):
    rsp = requests.get(url, timeout=timeout)
    if int(rsp.headers.get('X-RateLimit-Remaining', 1)) == 0:
        raise requests.RequestException('GitHub API Rate Limit exceeded')
    return rsp

def download(json):
    # Look for a matching asset (greaseweazle-firmware-<ver>.zip)
    for asset in json['assets']:
        url = asset['browser_download_url']
        m = re.match(r'.*/(greaseweazle-firmware-.+)\.zip$', url)
        if m is not None:
            basename = m.group(1)
            break
    # Download and unzip the asset
    name = basename+'.upd'
    print('Downloading latest firmware: '+name)
    rsp = gh_request_get(url, timeout=10)
    z = zipfile.ZipFile(io.BytesIO(rsp._content))
    return name, z.read(basename+'/'+name)


def download_by_tag(tag_name):
    '''Download the latest Update File from GitHub.'''
    rsp = gh_request_get('https://api.github.com/repos/keirf/'
                         'greaseweazle-firmware/releases', timeout=5)
    for release in rsp.json():
        if release['tag_name'] == tag_name:
            return download(release)
    raise error.Fatal("Unknown tag name '%s'" % tag_name)


def download_latest():
    '''Download the latest Update File from GitHub.'''
    rsp = gh_request_get('https://api.github.com/repos/keirf/'
                         'greaseweazle-firmware/releases/latest', timeout=5)
    return download(rsp.json())


def main(argv) -> None:

    epilog = """\
Examples:
  gw update
  gw update --force --tag v1.0
  gw update --file greaseweazle-firmware-v1.0.upd"""

    parser = util.ArgumentParser(usage='%(prog)s [options]',
                                 epilog=epilog)
    parser.add_argument("--file", help="use specified update file")
    parser.add_argument("--tag", help="use specified GitHub release tag")
    parser.add_argument("--device", help="device name (COM/serial port)")
    parser.add_argument("--force", action="store_true",
                        help="force update even if firmware is older")
    parser.add_argument("--bootloader", action="store_true",
                        help="update the bootloader (use with caution!)")
    parser.description = description
    parser.prog += ' ' + argv[1]
    args = parser.parse_args(argv[2:])

    error.check(args.tag is None or args.file is None,
                "File and tag both specified. Only one is allowed.")

    if args.tag is not None:
        args.file, dat = download_by_tag(args.tag)
    elif args.file is None:
        args.file, dat = download_latest()
    else:
        with open(args.file, "rb") as f:
            dat = f.read()

    try:
        usb = util.usb_open(args.device, mode_check=False)
        dat_version, dat = extract_update(usb, dat, args)
        print("Updating %s to version %u.%u..."
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
                raise SkipUpdate(
                    '''\
                    Device is already running version %d.%d.
                    Use --force to update anyway.''' % usb.version)
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
    except SkipUpdate as exc:
        print("** SKIPPING UPDATE:")
        print(textwrap.dedent(str(exc)))


if __name__ == "__main__":
    main(sys.argv)

# Local variables:
# python-indent: 4
# End:
