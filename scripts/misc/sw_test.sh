#!/bin/bash

# Creates a random Amiga ADF, writes the first three cylinders of a disk,
# dumps those cylinders back, and checks against original ADF.
dd if=/dev/urandom of=b.adf bs=512 count=1760
disk-analyse -e 2 b.adf a.adf
rm -f b.adf

# Write and verify ADF, Read ADF
gw --bt write --tracks="c=0-2" a.adf
gw --bt read --revs=1 --tracks="c=0-2" b.adf
disk-analyse -e 2 b.adf c.adf
diff a.adf c.adf
md5sum a.adf c.adf
rm -f b.adf c.adf

# Write SCP, Read SCP
disk-analyse a.adf a.scp
gw --bt write --tracks="c=0-2" a.scp
gw --bt read --revs=1 --tracks="c=0-2" b.scp
disk-analyse -e 2 b.scp b.adf
diff a.adf b.adf
md5sum a.adf b.adf
rm -f b.adf a.scp b.scp

# Write IPF, Read HFE
disk-analyse a.adf a.ipf
gw --bt write --tracks="c=0-2" a.ipf
gw --bt read --revs=1 --tracks="c=0-2" b.hfe
disk-analyse -e 2 b.hfe b.adf
diff a.adf b.adf
md5sum a.adf b.adf
rm -f b.adf a.ipf b.hfe

# Write HFE, Read HFE
disk-analyse a.adf a.hfe
gw --bt write --tracks="c=0-2" a.hfe
gw --bt read --revs=1 --tracks="c=0-2" b.hfe
disk-analyse -e 2 b.hfe b.adf
diff a.adf b.adf
md5sum a.adf b.adf

# Read Kryoflux
mkdir a
gw --bt read --revs=1 --tracks="c=0-2" a/
disk-analyse -e 2 a/ b.adf
diff a.adf b.adf
md5sum a.adf b.adf
rm -f b.adf c.adf a.hfe b.hfe
rm -rf a

rm -f a.adf
