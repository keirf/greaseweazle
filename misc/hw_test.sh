#!/bin/bash

# Creates a random Amiga ADF, writes the first three cylinders of a disk,
# dumps those cylinders back, and checks against original ADF.

dd if=/dev/urandom of=a.adf bs=512 count=1760
disk-analyse -e 2 a.adf b.adf
disk-analyse a.adf a.scp
./gw write --tracks=c=0-2 a.scp
./gw read --revs=1 --tracks=c=0-2 b.scp
disk-analyse -e 2 b.scp c.adf
diff b.adf c.adf
md5sum b.adf c.adf
rm -f a.adf b.adf c.adf a.scp b.scp
