#!/bin/bash
PYTHON="${PYTHON:-python3}"
$PYTHON -m pip install --user bitarray crcmod pyserial
(cd ./scripts/c_ext && $PYTHON setup.py install --install-platlib=../greaseweazle/optimised)
