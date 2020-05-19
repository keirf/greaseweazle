# greaseweazle/tools/bandwidth.py
#
# Greaseweazle control script: Measure USB bandwidth.
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

description = "Report the available USB bandwidth for the Greaseweazle device."

import sys

from timeit import default_timer as timer

from greaseweazle.tools import util
from greaseweazle import usb as USB

def measure_bandwidth(usb, args):
    print("                 Min   / Mean  / Max")

    w_nr = 1000000
    start = timer()
    usb.sink_bytes(w_nr)
    end = timer()
    av_bw = (w_nr * 8) / ((end-start) * 1000000)
    min_bw, max_bw = usb.bw_stats()
    print("Write Bandwidth: %.3f / %.3f / %.3f Mbps"
          % (min_bw, av_bw, max_bw))
    
    r_nr = 1000000
    start = timer()
    usb.source_bytes(r_nr)
    end = timer()
    av_bw = (r_nr * 8) / ((end-start) * 1000000)
    min_bw, max_bw = usb.bw_stats()
    print("Read Bandwidth:  %.3f / %.3f / %.3f Mbps"
          % (min_bw, av_bw, max_bw))

    twobyte_us = 249/72 # Smallest time requiring a 2-byte transmission code
    min_bw = 16 / twobyte_us # Bandwidth (Mbps) to transmit above time
    print("Minimum *consistent* bandwidth required: %.3f Mbps" % min_bw)

def main(argv):

    parser = util.ArgumentParser()
    parser.add_argument("device", nargs="?", default="auto",
                        help="serial device")
    parser.description = description
    parser.prog += ' ' + argv[1]
    args = parser.parse_args(argv[2:])

    try:
        usb = util.usb_open(args.device)
        measure_bandwidth(usb, args)
    except USB.CmdError as error:
        print("Command Failed: %s" % error)


if __name__ == "__main__":
    main(sys.argv)

# Local variables:
# python-indent: 4
# End:
