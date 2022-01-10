
export MAJOR := 0
export MINOR := 37

include Rules.mk

TARGETS := all clean dist _windist windist mrproper pysetup
.PHONY: $(TARGETS)

PROJ = greaseweazle-tools
VER := v$(MAJOR).$(MINOR)

all: scripts/greaseweazle/version.py

clean::
	rm -rf scripts/greaseweazle/optimised/optimised*
	rm -rf scripts/c_ext/*.egg-info scripts/c_ext/build
	rm -f scripts/greaseweazle/*.pyc
	rm -f scripts/greaseweazle/version.py
	find . -name __pycache__ | xargs rm -rf

dist: all
	rm -rf $(PROJ)-*
	mkdir -p $(PROJ)-$(VER)/scripts/greaseweazle/image
	mkdir -p $(PROJ)-$(VER)/scripts/greaseweazle/tools
	mkdir -p $(PROJ)-$(VER)/scripts/misc
	cp -a COPYING $(PROJ)-$(VER)/
	cp -a README $(PROJ)-$(VER)/
	cp -a gw $(PROJ)-$(VER)/
	cp -a scripts/49-greaseweazle.rules $(PROJ)-$(VER)/scripts/
	cp -a scripts/setup.sh $(PROJ)-$(VER)/scripts/
	cp -a scripts/gw.py $(PROJ)-$(VER)/scripts/
	cp -a scripts/greaseweazle $(PROJ)-$(VER)/scripts
	cp -a scripts/c_ext $(PROJ)-$(VER)/scripts
	cp -a scripts/misc/*.py $(PROJ)-$(VER)/scripts/misc/
	cp -a RELEASE_NOTES $(PROJ)-$(VER)/
	$(ZIP) $(PROJ)-$(VER).zip $(PROJ)-$(VER)

_windist:
	rm -rf ipf ipf.zip
	PYTHON=$(PYTHON) . ./scripts/setup.sh
	cp -a scripts/setup.py $(PROJ)-$(VER)/scripts
	cp -a scripts/greaseweazle/optimised/optimised* $(PROJ)-$(VER)/scripts/greaseweazle/optimised
	cd $(PROJ)-$(VER)/scripts && $(PYTHON) setup.py build
	cp -a $(PROJ)-$(VER)/scripts/build/exe.win*/* $(PROJ)-$(VER)/
	rm -rf $(PROJ)-$(VER)/scripts $(PROJ)-$(VER)/*.py $(PROJ)-$(VER)/gw
	curl -L http://softpres.org/_media/files:spsdeclib_5.1_windows.zip --output ipf.zip
	$(UNZIP) -oipf ipf.zip
	cp -a ipf/capsimg_binary/CAPSImg.dll $(PROJ)-$(VER)/
	rm -rf ipf ipf.zip
	$(ZIP) $(PROJ)-$(VER)-win.zip $(PROJ)-$(VER)

windist:
	$(MAKE) dist
	$(MAKE) _windist

mrproper: clean
	rm -rf $(PROJ)-* ipf ipf.zip

scripts/greaseweazle/version.py: Makefile
	echo "major = $(MAJOR)" >$@
	echo "minor = $(MINOR)" >>$@
