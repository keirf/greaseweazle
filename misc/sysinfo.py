import platform, sys
import serial.tools.list_ports

# MacOS Catalina:
#  platform.system == "Darwin"
#  Attrs: device, manufacturer, product, vid, pid, location, serial_number
#
# Ubuntu 18.04:
#  platform.system == "Linux"
#  Attrs: device, manufacturer, product, vid, pid, location, serial_number
#
# Windows 7:
#  platform.system, platform.release == "Windows", "7"
#  Attrs: device, vid, pid, location, serial_number
#   (manufacturer == "InterBiometrics")
#
# Windows 10:
#  platform.system, platform.release == "Windows", "10"
#  Attrs: device, vid, pid, location, serial_number
#   (manufacturer == "Microsoft")

print("platform.system: %s" % platform.system())
print("platform.version: %s" % platform.version())
print("platform.release: %s" % platform.release())

ports = serial.tools.list_ports.comports()
i = 0
for port in ports:
    i += 1
    print("Port %d:" % i)
    if port.device:
        print("    device: '%s'" % port.device)
    if port.name:
        print("    name: '%s'" % port.name)
    if port.hwid:
        print("    hwid: '%s'" % port.hwid)
    if port.manufacturer:
        print("    manufacturer: '%s'" % port.manufacturer)
    if port.product:
        print("    product: '%s'" % port.product)
    if port.vid:
        print("    vid: %04x" % port.vid)
    if port.pid:
        print("    pid: %04x" % port.pid)
    if port.location:
        print("    location: '%s'" % port.location)
    if port.serial_number:
        print("    serial_number: '%s'" % port.serial_number)
    if port.interface:
        print("    interface: '%s'" % port.interface)

if len(sys.argv) < 2 or sys.argv[1] != "loop":
    sys.exit(0)

# Loop checking that .location is always valid for a Weazle
while True:
    for port in serial.tools.list_ports.comports():
        if port.vid == 0x1209:
            if not port.location:
                print("BAD", flush=True)
            else:
                print(".", end="", flush=True)

