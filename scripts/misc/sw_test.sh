#!/bin/bash

# Creates a random Amiga ADF, writes the first three cylinders of a disk,
# dumps those cylinders back, and checks against original ADF.

# Write SCP, Read SCP
dd if=/dev/urandom of=a.adf bs=512 count=1760
disk-analyse -e 2 a.adf b.adf
disk-analyse a.adf a.scp
python3 gw.py write --ecyl=2 a.scp
python3 gw.py read --revs=1 --ecyl=2 b.scp
disk-analyse -e 2 b.scp c.adf
diff b.adf c.adf
md5sum b.adf c.adf
rm -f a.adf b.adf c.adf a.scp b.scp

# Write IPF, Read HFE
dd if=/dev/urandom of=a.adf bs=512 count=1760
disk-analyse -e 2 a.adf b.adf
disk-analyse a.adf a.ipf
python3 gw.py write --ecyl=2 a.ipf
python3 gw.py read --revs=1 --ecyl=2 b.hfe
disk-analyse -e 2 b.hfe c.adf
diff b.adf c.adf
md5sum b.adf c.adf
rm -f a.adf b.adf c.adf a.ipf b.hfe

# Write HFE, Read HFE
dd if=/dev/urandom of=a.adf bs=512 count=1760
disk-analyse -e 2 a.adf b.adf
disk-analyse a.adf a.hfe
python3 gw.py write --ecyl=2 a.hfe
python3 gw.py read --revs=1 --ecyl=2 b.hfe
disk-analyse -e 2 b.hfe c.adf
diff b.adf c.adf
md5sum b.adf c.adf
rm -f a.adf b.adf c.adf a.hfe b.hfe

