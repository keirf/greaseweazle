
export FW_MAJOR := 0
export FW_MINOR := 34

TARGETS := all clean dist windist mrproper pysetup
.PHONY: $(TARGETS)

ifneq ($(RULES_MK),y)

export ROOT := $(CURDIR)

$(TARGETS):
	$(MAKE) -f $(ROOT)/Rules.mk $@

else

PROJ = greaseweazle-tools
VER := v$(FW_MAJOR).$(FW_MINOR)

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

windist: pysetup
	rm -rf $(PROJ)-$(VER) ipf ipf.zip
	[ -e $(PROJ)-$(VER).zip ] || \
	curl -L https://github.com/keirf/greaseweazle/releases/download/$(VER)/$(PROJ)-$(VER).zip --output $(PROJ)-$(VER).zip
	$(UNZIP) $(PROJ)-$(VER).zip
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

mrproper: clean
	rm -rf $(PROJ)-* ipf ipf.zip

scripts/greaseweazle/version.py: Makefile
	echo "major = $(FW_MAJOR)" >$@
	echo "minor = $(FW_MINOR)" >>$@

pysetup: scripts/greaseweazle/version.py
	PYTHON=$(PYTHON) . ./scripts/setup.sh

endif
