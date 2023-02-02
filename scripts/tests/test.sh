
SCRIPTS=scripts/tests

# Static type checking
python3 -m pip install --user mypy types-requests .
echo "__version__: str" >src/greaseweazle/__init__.py
python3 -m mypy --config-file=$SCRIPTS/mypy.ini
rm -f $src/greaseweazle/__init__.py

cd $SCRIPTS
dd if=/dev/urandom of=olivetti_m20.img bs=1024 count=280
gw convert --format=olivetti.m20 olivetti_m20.img a.imd
gw convert --format=olivetti.m20 a.imd a1.hfe
gw convert a.imd a2.hfe
gw convert --format=olivetti.m20 a1.hfe a1.img
gw convert --format=olivetti.m20 a2.hfe a2.img
diff -u a1.img a2.img
# Punch padding holes in the original IMG before we diff
for i in 1 3 5 7 9 11 13 15 17 19 21 23 25 27 29 31 ; do
    dd if=/dev/zero of=olivetti_m20.img bs=128 seek=$i count=1 conv=notrunc;
done
diff -u a1.img olivetti_m20.img
rm -f *.img *.hfe *.imd

dd if=/dev/urandom of=a.adf bs=1024 count=880
gw convert a.adf a.scp
gw convert a.scp b.adf
diff -u a.adf b.adf
rm -f *.adf *.scp
