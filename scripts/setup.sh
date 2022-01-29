#!/bin/bash
PYTHON="${PYTHON:-python3}"
if [ ! -d ./scripts/c_ext ]; then
    echo "** Please run setup.sh from within the Greaseweazle folder";
    echo "** eg: ./scripts/setup.sh";
    exit 1;
fi ;
$PYTHON -m pip install --user bitarray crcmod pyserial requests wheel
$PYTHON -m pip install ./scripts/c_ext --target=./scripts/greaseweazle/optimised --upgrade
