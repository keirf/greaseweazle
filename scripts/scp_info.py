import struct, sys

trknr = int(sys.argv[2])

with open(sys.argv[1], "rb") as f:
    dat = f.read()

header = struct.unpack("<3s9BI", dat[0:16])
(sig, _, _, nr_revs, s_trk, e_trk, flags, _, ss, _, _) = header
assert sig == b"SCP"
nr_sides = 1 if ss else 2
        
trk_offs = struct.unpack("<168I", dat[16:0x2b0])

print("Revolutions: %u" % nr_revs)
print("Track %u:" % trknr)

trk_off = trk_offs[trknr]
if trk_off == 0:
    print("Empty")
    sys.exit(0)
    
# Parse the SCP track header and extract the flux data.
thdr = dat[trk_off:trk_off+4+12*nr_revs]
sig, tnr, _, _, s_off = struct.unpack("<3sB3I", thdr[:16])
assert sig == b"TRK"
assert tnr == trknr
for i in range(nr_revs):
    t,n,_ = struct.unpack("<3I", thdr[4+i*12:4+(i+1)*12])
    print("Rev %u: time=%uus flux=%u" % (i, t//40, n))
_, e_nr, e_off = struct.unpack("<3I", thdr[-12:])
tdat = dat[trk_off+s_off:trk_off+e_off+e_nr*2]
fluxl = []
while tdat:
    flux, = struct.unpack(">H", tdat[:2])
    tdat = tdat[2:]
    fluxl.append(flux / 40)
tot = 0.0
for x in fluxl:
    print(x)
    tot += x
print("Total: %uus (%uus per rev)" % (int(tot), tot//nr_revs))

