set -e

GW="gw --bt"

rm -rf .test
mkdir -p .test
pushd .test

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

dd if=/dev/urandom of=a.adf bs=1024 count=880
$GW convert a.adf a.scp
$GW convert a.scp b.adf
diff -u a.adf b.adf

popd
