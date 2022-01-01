ifeq ($(OS), Windows_NT)
PYTHON = python
ZIP = "C:/Program Files/7-Zip/7z.exe" a
UNZIP = "C:/Program Files/7-Zip/7z.exe" x
else
PYTHON = python3
ZIP = zip -r
UNZIP = unzip
endif

.SECONDARY:
