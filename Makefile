
include Rules.mk

TARGETS := version install clean _dist dist windist mrproper
.PHONY: $(TARGETS)

PROJ = greaseweazle-tools
VER := $(shell $(PYTHON) -c \
"from setuptools_scm import get_version ; print('v'+get_version())")

version:
	@echo $(VER)

install:
	$(PYTHON) -m pip install .

clean:
	rm -rf build dist
	rm -rf src/*.egg-info

_dist:
	rm -rf $(PROJ)-*
	mkdir -p $(PROJ)-$(VER)
	cp -a COPYING $(PROJ)-$(VER)/
	cp -a README $(PROJ)-$(VER)/
	cp -a RELEASE_NOTES $(PROJ)-$(VER)/
	echo $(VER) >$(PROJ)-$(VER)/VERSION

dist: _dist
	mkdir -p $(PROJ)-$(VER)/scripts/misc
	$(PYTHON) setup.py sdist -d $(PROJ)-$(VER)
	cp -a scripts/49-greaseweazle.rules $(PROJ)-$(VER)/scripts/
	cp -a scripts/misc/*.py $(PROJ)-$(VER)/scripts/misc/
	$(ZIP) $(PROJ)-$(VER).zip $(PROJ)-$(VER)

windist: _dist install
	rm -rf ipf ipf.zip
	cd scripts/win && $(PYTHON) setup.py build
	cp -a scripts/win/build/exe.win*/* $(PROJ)-$(VER)/
	curl -L http://softpres.org/_media/files:spsdeclib_5.1_windows.zip --output ipf.zip
	$(UNZIP) -oipf ipf.zip
	cp -a ipf/capsimg_binary/CAPSImg.dll $(PROJ)-$(VER)/
	rm -rf ipf ipf.zip
	$(ZIP) $(PROJ)-$(VER)-win.zip $(PROJ)-$(VER)

mrproper: clean
	rm -rf $(PROJ)-* ipf ipf.zip
