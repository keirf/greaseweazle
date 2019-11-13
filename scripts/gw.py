# gw.py
#
# Greaseweazle control script.
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

#from timeit import default_timer as timer
import os, sys, struct, argparse, serial
import crcmod.predefined

from greaseweazle import version
from greaseweazle import usb as USB
from greaseweazle.scp import SCP
from greaseweazle.hfe import HFE

def get_image_class(name):
    image_types = { '.scp': SCP, '.hfe': HFE }
    _, ext = os.path.splitext(name)
    if not ext.lower() in image_types:
        print("**Error: Unrecognised file suffix '%s'" % ext)
        return None
    return image_types[ext.lower()]

# read_to_image:
# Reads a floppy disk and dumps it into a new image file.
def read_to_image(usb, args):

    image_class = get_image_class(args.file)
    if not image_class:
        return
    image = image_class(args.scyl, args.nr_sides)

    for cyl in range(args.scyl, args.ecyl+1):
        for side in range(0, args.nr_sides):

            print("\rReading Track %u.%u..." % (cyl, side), end="")
            usb.seek(cyl, side)

            # Physically read the track.
            for retry in range(1, 5):
                ack, flux = usb.read_track(args.revs)
                if ack == USB.Ack.Okay:
                    break
                elif ack == USB.Ack.FluxOverflow and retry < 5:
                    print("Retry #%u..." % (retry))
                else:
                    raise CmdError(ack)
                
            # Stash the data for later writeout to the image file.
            image.append_track(flux)

    print()

    # Write the image file.
    with open(args.file, "wb") as f:
        f.write(image.get_image())


# write_from_image:
# Writes the specified image file to floppy disk.
def write_from_image(usb, args):

    if args.adjust_speed:
        # @drive_ticks is the time in Gresaeweazle ticks between index pulses.
        # We will adjust the flux intervals per track to allow for this.
        for retry in range(1, 5):
            ack, flux = usb.read_track(2)
            if ack == USB.Ack.Okay:
                break
            elif ack != USB.Ack.FluxOverflow or retry >= 5:
                raise CmdError(ack)
        drive_ticks = (flux.index_list[0] + flux.index_list[1]) / 2
        del flux

    # Read and parse the image file.
    image_class = get_image_class(args.file)
    if not image_class:
        return
    with open(args.file, "rb") as f:
        image = image_class.from_file(f.read())

    for cyl in range(args.scyl, args.ecyl+1):
        for side in range(0, args.nr_sides):

            flux = image.get_track(cyl, side, writeout=True)
            if not flux:
                continue

            print("\rWriting Track %u.%u..." % (cyl, side), end="")
            usb.seek(cyl, side)

            if args.adjust_speed:
                # @factor adjusts flux times for speed variations between the
                # read-in and write-out drives.
                factor = drive_ticks / flux.index_list[0]
            else:
                # Simple ratio between the GW and image sample frequencies.
                factor = usb.sample_freq / flux.sample_freq

            # Convert the flux samples to Greaseweazle sample frequency.
            rem = 0.0
            flux_list = []
            for x in flux.list:
                y = x * factor + rem
                val = int(round(y))
                rem = y - val
                flux_list.append(val)

            # Encode the flux times for Greaseweazle, and write them out.
            enc_flux = usb.encode_flux(flux_list)
            for retry in range(1, 5):
                ack = usb.write_track(enc_flux)
                if ack == USB.Ack.Okay:
                    break
                elif ack == USB.Ack.FluxUnderflow and retry < 5:
                    print("Retry #%u..." % (retry))
                else:
                    raise CmdError(ack)

    print()


# update_firmware:
# Updates the Greaseweazle firmware using the specified Update File.
def update_firmware(usb, args):

    # Check that an update operation was actually requested.
    if args.action != "update":
        print("Greaseweazle is in Firmware Update Mode:")
        print(" The only available action is \"update <update_file>\"")
        if usb.update_jumpered:
            print(" Remove the Update Jumper for normal operation")
        else:
            print(" Main firmware is erased: You *must* perform an update!")
        return

    # Check that the firmware is actually in update mode.
    if not usb.update_mode:
        print("Greaseweazle is in Normal Mode:")
        print(" To \"update\" you must install the Update Jumper")
        return

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


# _main:
# Argument processing and dispatch.
def _main(argv):

    actions = {
        "read" : read_to_image,
        "write" : write_from_image,
        "update" : update_firmware
    }

    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("action")
    parser.add_argument("--revs", type=int, default=3,
                        help="number of revolutions to read per track")
    parser.add_argument("--scyl", type=int, default=0,
                        help="first cylinder to read/write")
    parser.add_argument("--ecyl", type=int, default=81,
                        help="last cylinder to read/write")
    parser.add_argument("--single-sided", action="store_true",
                        help="read/write a single-sided image")
    parser.add_argument("--adjust-speed", action="store_true",
                        help="adjust write-flux times for drive speed")
    parser.add_argument("file", help="in/out filename")
    parser.add_argument("device", help="serial device")
    args = parser.parse_args(argv[1:])
    args.nr_sides = 1 if args.single_sided else 2

    if not args.action in actions:
        print("** Action \"%s\" is not recognised" % args.action)
        print("Valid actions: ", end="")
        print(", ".join(str(key) for key in actions.keys()))
        return

    usb = USB.Unit(serial.Serial(args.device))

    print("** %s v%u.%u, Host Tools v%u.%u"
          % (("Greaseweazle", "Bootloader")[usb.update_mode],
             usb.major, usb.minor,
             version.major, version.minor))

    if args.action == "update" or usb.update_mode:
        actions[args.action](usb, args)
        return

    elif usb.update_needed:
        print("Firmware is out of date: Require v%u.%u"
              % (version.major, version.minor))
        print("Install the Update Jumper and \"update <update_file>\"")
        return

    #usb.step_delay = 5000
    #print("Select Delay: %uus" % usb.select_delay)
    #print("Step Delay: %uus" % usb.step_delay)
    #print("Settle Time: %ums" % usb.seek_settle_delay)
    #print("Motor Delay: %ums" % usb.motor_delay)
    #print("Auto Off: %ums" % usb.auto_off_delay)

    try:
        usb.drive_select(True)
        usb.drive_motor(True)
        actions[args.action](usb, args)
    except KeyboardInterrupt:
        print()
        usb.reset()
        usb.ser.close()
        usb.ser.open()
    finally:
        usb.drive_motor(False)
        usb.drive_select(False)


def main(argv):
    try:
        _main(argv)
    except USB.CmdError as error:
        print("Command Failed: %s" % error)


if __name__ == "__main__":
    main(sys.argv)

# Local variables:
# python-indent: 4
# End:
