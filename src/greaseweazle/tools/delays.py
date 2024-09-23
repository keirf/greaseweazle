# greaseweazle/tools/delays.py
#
# Greaseweazle control script: Get/Set Delay Timers.
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

description = "Display (and optionally modify) drive-delay parameters."

import sys, struct

from greaseweazle.tools import util
from greaseweazle import usb as USB
from greaseweazle import error


class Delays:
    def __init__(self, usb: USB.Unit) -> None:
        self.usb = usb
        try:
            self.size = 14
            dat = usb.get_params(USB.Params.Delays, 14)
        except USB.CmdError as err:
            if err.code != USB.Ack.BadCommand:
                raise err
            self.size = 10
            dat = usb.get_params(USB.Params.Delays, 10) + bytes(4)

        (self.select, self.step, self.seek_settle, self.motor, self.watchdog,
         self.pre_write, self.post_write) = struct.unpack('<7H', dat)
    def update(self) -> None:
        dat = struct.pack('<7H', self.select, self.step, self.seek_settle,
                          self.motor, self.watchdog,
                          self.pre_write, self.post_write)
        self.usb.set_params(USB.Params.Delays, dat[:self.size])

def print_info_line(name: str, value: str, tab=0) -> None:
    print(''.ljust(tab) + (name + ':').ljust(14-tab) + value)

def main(argv) -> None:

    epilog = '''
Select Delay:      Delay (usec) after asserting drive select
Step Delay:        Delay (usec) after issuing a head-step command
Settle Time:       Delay (msec) after completing a head-seek operation
Motor Delay:       Delay (msec) after turning on drive spindle motor
Watchdog:          Timeout (msec) since last command upon which all
                   drives are deselected and spindle motors turned off
Pre-Write:         Min. usec from track change to write start
Post-Write:        Min. usec from write end to track change'''
    
    parser = util.ArgumentParser(usage='%(prog)s [options]',
                                 epilog=epilog)
    parser.add_argument("--device", help="device name (COM/serial port)")
    parser.add_argument("--select", type=util.uint, metavar="N",
                        help="Select Delay (usecs)")
    parser.add_argument("--step", type=util.uint, metavar="N",
                        help="Step Delay (usecs)")
    parser.add_argument("--settle", type=util.uint, metavar="N",
                        help="Settle Time (msecs)")
    parser.add_argument("--motor", type=util.uint, metavar="N",
                        help="Motor Delay (msecs)")
    parser.add_argument("--watchdog", type=util.uint, metavar="N",
                        help="Watchdog (msecs)")
    parser.add_argument("--pre-write", type=util.uint, metavar="N",
                        help="Pre-Write (usecs)")
    parser.add_argument("--post-write", type=util.uint, metavar="N",
                        help="Post-Write (usecs)")
    parser.description = description
    parser.prog += ' ' + argv[1]
    args = parser.parse_args(argv[2:])

    try:

        usb = util.usb_open(args.device)

        delays = Delays(usb)

        update = False
        
        if args.select:
            delays.select = args.select
            update = True
        if args.step:
            delays.step = args.step
            update = True
        if args.settle:
            delays.seek_settle = args.settle
            update = True
        if args.motor:
            delays.motor = args.motor
            update = True
        if args.watchdog:
            delays.watchdog = args.watchdog
            update = True
        if args.pre_write:
            error.check(delays.size >= 14,
                        'Option --pre-write requires updated firmware')
            delays.pre_write = args.pre_write
            update = True
        if args.post_write:
            error.check(delays.size >= 14,
                        'Option --post-write requires updated firmware')
            delays.post_write = args.post_write
            update = True

        if update:
            delays.update()

        print_info_line('Select Delay', f'{delays.select}us')
        print_info_line('Step Delay', f'{delays.step}us')
        print_info_line('Settle Time', f'{delays.seek_settle}ms')
        print_info_line('Motor Delay', f'{delays.motor}ms')
        print_info_line('Watchdog', f'{delays.watchdog}ms')
        if delays.size >= 14:
            print_info_line('Pre-Write', f'{delays.pre_write}us')
            print_info_line('Post-Write', f'{delays.post_write}us')

    except USB.CmdError as err:
        print("Command Failed: %s" % err)


if __name__ == "__main__":
    main(sys.argv)

# Local variables:
# python-indent: 4
# End:
