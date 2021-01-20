#!/bin/bash
PYTHON="${PYTHON:-python3}"
if [ ! -d ./scripts/c_ext ]; then
    echo "** Please run setup.sh from within the Greaseweazle folder";
    echo "** eg: ./scripts/setup.sh";
    exit 1;
fi ;
$PYTHON -m pip install --user bitarray crcmod pyserial
(cd ./scripts/c_ext && $PYTHON setup.py install --install-platlib=../greaseweazle/optimised)
