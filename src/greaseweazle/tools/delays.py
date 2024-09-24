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
        self.size = 16
        while True:
            try:
                dat = usb.get_params(USB.Params.Delays, self.size)
                break
            except USB.CmdError as err:
                if err.code != USB.Ack.BadCommand or self.size == 10:
                    raise err
                self.size -= 2
        dat += bytes(16 - self.size)
        (self.select, self.step, self.seek_settle, self.motor, self.watchdog,
         self.pre_write, self.post_write, self.index_mask
         ) = struct.unpack('<8H', dat)
        if self.size < 12: self.pre_write = None
        if self.size < 14: self.post_write = None
        if self.size < 16: self.index_mask = None

    def update(self) -> None:
        dat = struct.pack('<5H', self.select, self.step, self.seek_settle,
                          self.motor, self.watchdog)
        if self.pre_write is not None:
            dat += struct.pack('<H', self.pre_write)
        if self.post_write is not None:
            dat += struct.pack('<H', self.post_write)
        if self.index_mask is not None:
            dat += struct.pack('<H', self.index_mask)
        assert len(dat) == self.size
        self.usb.set_params(USB.Params.Delays, dat)


def print_info_line(name: str, value: str, tab=0) -> None:
    print(''.ljust(tab) + (name + ':').ljust(14-tab) + value)


def main(argv) -> None:

    epilog = '''
Select Delay: (usec) Delay after asserting drive select
Step Delay:   (usec) Delay after issuing a head-step command
Settle Time:  (msec) Delay after completing a head-seek operation
Motor Delay:  (msec) Delay after turning on drive spindle motor
Watchdog:     (msec) Timeout since last command upon which all drives
                     are deselected and spindle motors turned off
Pre-Write:    (usec) Min. time from track change to write start
Post-Write:   (usec) Min. time from write end to track change
Index Mask:   (usec) Index post-trigger mask time'''
    
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
    parser.add_argument("--index-mask", type=util.uint, metavar="N",
                        help="Index Mask (usecs)")
    parser.description = description
    parser.prog += ' ' + argv[1]
    args = parser.parse_args(argv[2:])

    try:

        usb = util.usb_open(args.device)

        delays = Delays(usb)

        update = False
        
        if args.select is not None:
            delays.select = args.select
            update = True
        if args.step is not None:
            delays.step = args.step
            update = True
        if args.settle is not None:
            delays.seek_settle = args.settle
            update = True
        if args.motor is not None:
            delays.motor = args.motor
            update = True
        if args.watchdog is not None:
            delays.watchdog = args.watchdog
            update = True
        if args.pre_write is not None:
            error.check(delays.pre_write is not None,
                        'Option --pre-write requires updated firmware')
            delays.pre_write = args.pre_write
            update = True
        if args.post_write is not None:
            error.check(delays.post_write is not None,
                        'Option --post-write requires updated firmware')
            delays.post_write = args.post_write
            update = True
        if args.index_mask is not None:
            error.check(delays.index_mask is not None,
                        'Option --index-mask requires updated firmware')
            delays.index_mask = args.index_mask
            update = True

        if update:
            delays.update()

        print_info_line('Select Delay', f'{delays.select}us')
        print_info_line('Step Delay', f'{delays.step}us')
        print_info_line('Settle Time', f'{delays.seek_settle}ms')
        print_info_line('Motor Delay', f'{delays.motor}ms')
        print_info_line('Watchdog', f'{delays.watchdog}ms')
        if delays.pre_write is not None:
            print_info_line('Pre-Write', f'{delays.pre_write}us')
        if delays.post_write is not None:
            print_info_line('Post-Write', f'{delays.post_write}us')
        if delays.index_mask is not None:
            print_info_line('Index Mask', f'{delays.index_mask}us')

    except USB.CmdError as err:
        print("Command Failed: %s" % err)


if __name__ == "__main__":
    main(sys.argv)

# Local variables:
# python-indent: 4
# End:
