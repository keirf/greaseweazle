# greaseweazle/tools/bandwidth.py
#
# Greaseweazle control script: Measure USB bandwidth.
#
# Written & released by Keir Fraser <keir.xen@gmail.com>
#
# This is free and unencumbered software released into the public domain.
# See the file COPYING for more details, or visit <http://unlicense.org>.

description = "Report the available USB bandwidth for the Greaseweazle device."

import struct, sys

from timeit import default_timer as timer

from greaseweazle.tools import util
from greaseweazle import usb as USB

def generate_random_buffer(nr: int, seed: int) -> bytes:
    dat = bytearray()
    r = seed
    for i in range(nr):
        dat.append(r&255)
        if r & 1:
            r = (r>>1) ^ 0x80000062
        else:
            r >>= 1
    return dat

def measure_bandwidth(usb, args) -> None:
    print()
    print("%19s%-7s/   %-7s/   %-7s" % ("", "Min.", "Mean", "Max."))

    seed = 0x12345678
    w_nr = r_nr = 1000000
    buf = generate_random_buffer(w_nr, seed)

    start = timer()
    ack = usb.sink_bytes(buf, seed)
    end = timer()
    av_w_bw = (w_nr * 8) / ((end-start) * 1e6)
    min_w_bw, max_w_bw = usb.bw_stats()
    print("Write Bandwidth: %8.3f / %8.3f / %8.3f Mbps"
          % (min_w_bw, av_w_bw, max_w_bw))
    if ack != 0:
        print("ERROR: USB write data garbled (Host -> Device)")
        return
    
    start = timer()
    sbuf = usb.source_bytes(r_nr, seed)
    end = timer()
    av_r_bw = (r_nr * 8) / ((end-start) * 1e6)
    min_r_bw, max_r_bw = usb.bw_stats()
    print("Read Bandwidth:  %8.3f / %8.3f / %8.3f Mbps"
          % (min_r_bw, av_r_bw, max_r_bw))
    if sbuf is not None and sbuf != buf:
        print("ERROR: USB read data garbled (Device -> Host)")
        return

    est_min_bw = 0.9 * min(min_r_bw, min_w_bw)
    print()
    print("Estimated Consistent Min. Bandwidth: %.3f Mbps" % est_min_bw)
    max_flux_rate = ((est_min_bw * 0.9) * 1e6) / 8
    
    twobyte_us = 249/72 # Smallest time requiring a 2-byte transmission code
    req_min_bw = 16 / twobyte_us # Bandwidth (Mbps) to transmit above time
    if req_min_bw > est_min_bw:
        print(" -> **WARNING** BELOW REQUIRED MIN.: %.3f Mbps" % req_min_bw)
    else:
        print(" -> Max. Flux Rate: %.3f Msamples/sec"
              % (max_flux_rate / 1e6))
        print(" -> Min. Ave. Flux: %.3f us"
              % (1e6 / max_flux_rate))

def main(argv) -> None:

    parser = util.ArgumentParser(usage='%(prog)s [options]')
    parser.add_argument("--device", help="device name (COM/serial port)")
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
