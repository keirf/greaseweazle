python3 -m pip install --user mypy types-requests .
echo "__version__: str" >src/greaseweazle/__init__.py
make mypy
rm -f $src/greaseweazle/__init__.py
