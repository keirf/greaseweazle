set -e

GW="gw --bt"

rm -rf .test
mkdir -p .test
pushd .test

# IBM
dd if=/dev/urandom of=olivetti_m20.img bs=1024 count=280
$GW convert --format=olivetti.m20 olivetti_m20.img a.imd
$GW convert --format=olivetti.m20 a.imd a1.hfe
$GW convert a.imd a2.hfe
$GW convert --format=olivetti.m20 a1.hfe a1.img
$GW convert --format=olivetti.m20 a2.hfe a2.img
diff -u a1.img a2.img
# Punch padding holes in the original IMG before we diff
for i in 1 3 5 7 9 11 13 15 17 19 21 23 25 27 29 31 ; do
    dd if=/dev/zero of=olivetti_m20.img bs=128 seek=$i count=1 conv=notrunc;
done
diff -u a1.img olivetti_m20.img

# Amiga
dd if=/dev/urandom of=a.adf bs=1024 count=880
mkdir a
$GW convert a.adf a/00.0.raw
$GW convert a/00.0.raw b.adf
diff -u a.adf b.adf

# C64
dd if=/dev/urandom of=a.d64 bs=256 count=683
$GW convert --tracks=c=0-34 a.d64 a.scp::revs=1
$GW convert a.scp b.d64
diff -u a.d64 b.d64

# Mac
dd if=/dev/urandom of=a.img bs=1024 count=800
$GW convert --format=mac.800 a.img a.scp::revs=1
$GW convert --format=mac.800 a.scp b.img
diff -u a.img b.img

# Bitcell
$GW convert --format=raw.250 a.scp a.hfe

# DEC-RX02
dd if=/dev/urandom of=rx02.img bs=256 count=2002
$GW convert --format=dec.rx02 rx02.img rx02_a.scp
$GW convert --format=dec.rx02 rx02_a.scp rx02_a.img 2>&1 | tee rx02.log
diff -u rx02.img rx02_a.img
grep Unknown rx02.log && exit 1

# FDI import
echo -en "\x00\x00\x00\x00\x90\x00\x00\x00" >a.fdi
echo -en "\x00\x10\x00\x00\x00\x40\x13\x00" >>a.fdi
echo -en "\x00\x04\x00\x00\x08\x00\x00\x00" >>a.fdi
echo -en "\x02\x00\x00\x00\x4d\x00\x00\x00" >>a.fdi
dd if=/dev/zero of=a.fdi bs=16 seek=2 count=254
dd if=/dev/urandom of=a.img bs=4096 count=308
cat a.img >>a.fdi
$GW convert a.fdi a.scp
$GW convert --format=pc98.2hd a.scp b.img
diff -u a.img b.img

popd
