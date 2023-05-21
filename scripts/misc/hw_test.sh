#!/bin/bash

# Creates a random Amiga ADF, then writes three cylinders with verification.

dd if=/dev/urandom of=a.adf bs=512 count=1760
gw write --tracks=c=38-40 a.adf
