import struct, sys
import matplotlib.pyplot as plt

NO_DAT    = 0
PRINT_DAT = 1
PLOT_DAT  = 2

def decode_flux(tdat):
    flux, fluxl = 0, []
    while tdat:
        f, = struct.unpack(">H", tdat[:2])
        tdat = tdat[2:]
        if f == 0:
            flux += 65536
        else:
            flux += f
            fluxl.append(flux / 40)
            flux = 0
    return fluxl

def dump_track(dat, trk_offs, trknr, show_dat):
    print("Track %u:" % trknr)

    trk_off = trk_offs[trknr]
    if trk_off == 0:
        print("Empty")
        return
    
    # Parse the SCP track header and extract the flux data.
    thdr = dat[trk_off:trk_off+4+12*nr_revs]
    sig, tnr, _, _, s_off = struct.unpack("<3sB3I", thdr[:16])
    assert sig == b"TRK"
    assert tnr == trknr
    p_idx, tot = [], 0.0
    for i in range(nr_revs):
        t,n,off = struct.unpack("<3I", thdr[4+i*12:4+(i+1)*12])
        flux = decode_flux(dat[trk_off+off:trk_off+off+n*2])
        print("Rev %u: time=%.2fus nr_flux=%u tot_flux=%.2fus"
              % (i, t/40, n, sum(flux)))
        tot += t/40
        p_idx.append(tot)
    if not show_dat:
        return
    
    _, e_nr, e_off = struct.unpack("<3I", thdr[-12:])
    fluxl = decode_flux(dat[trk_off+s_off:trk_off+e_off+e_nr*2])
    tot = 0.0
    i = 0
    px, py = [], []
    for x in fluxl:
        if show_dat == PRINT_DAT:
            bad = ""
            if (x < 3.6) or ((x > 4.4) and (x < 5.4)) \
               or ((x > 6.6) and (x < 7.2)) or (x > 8.8):
                bad = "BAD"
            print("%d: %f %s" % (i, x, bad))
        elif x < 50:
            px.append(tot/1000)
            py.append(x)
        i += 1
        tot += x
    print("Total: %uus (%uus per rev)" % (int(tot), tot//nr_revs))
    if show_dat == PLOT_DAT:
        plt.xlabel("Time (ms)")
        plt.ylabel("Flux (us)")
        plt.gcf().set_size_inches(12, 8)
        plt.axvline(x=0, ymin=0.95, color='r')
        for t in p_idx:
            plt.axvline(x=t/1000, ymin=0.95, color='r')
        plt.scatter(px, py, s=1)
        plt.ylim((0, None))
        plt.show()

argv = sys.argv

plot = (argv[1] == '--plot')
if plot:
    argv = argv[1:]

with open(argv[1], "rb") as f:
    dat = f.read()

header = struct.unpack("<3s9BI", dat[0:16])
(sig, _, _, nr_revs, s_trk, e_trk, flags, _, ss, _, _) = header
assert sig == b"SCP"
nr_sides = 1 if ss else 2
        
trk_offs = struct.unpack("<168I", dat[16:0x2b0])

print("Revolutions: %u" % nr_revs)

if len(argv) == 3:
    dump_track(dat, trk_offs, int(argv[2]), PLOT_DAT if plot else PRINT_DAT)
else:
    for i in range(s_trk, e_trk+1):
        dump_track(dat, trk_offs, i, NO_DAT)

