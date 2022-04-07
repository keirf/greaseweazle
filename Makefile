
include Rules.mk

TARGETS := version install uninstall clean _dist dist windist mrproper
.PHONY: $(TARGETS)

PROJ = greaseweazle
VER := $(shell $(PYTHON) -c \
"from setuptools_scm import get_version ; print(get_version())")

version:
	@echo $(VER)

install:
	$(PYTHON) -m pip install .

uninstall:
	$(PYTHON) -m pip uninstall $(PROJ)

clean:
	rm -rf build dist
	rm -rf src/*.egg-info src/greaseweazle/optimised/*.so
	rm -rf $(PROJ)-* ipf ipf.zip
	find src -name __pycache__ | xargs rm -rf

dist:
	rm -rf $(PROJ)-*
	$(PYTHON) setup.py sdist --formats=zip -d .

windist: install
	rm -rf $(PROJ)-*
	mkdir -p $(PROJ)-$(VER)
	cp -a COPYING $(PROJ)-$(VER)/
	cp -a README $(PROJ)-$(VER)/
	cp -a RELEASE_NOTES $(PROJ)-$(VER)/
	echo $(VER) >$(PROJ)-$(VER)/VERSION
	rm -rf ipf ipf.zip
	cd scripts/win && $(PYTHON) setup.py build
	cp -a scripts/win/build/exe.win*/* $(PROJ)-$(VER)/
	curl -L http://softpres.org/_media/files:spsdeclib_5.1_windows.zip --output ipf.zip
	$(UNZIP) -oipf ipf.zip
	cp -a ipf/capsimg_binary/CAPSImg.dll $(PROJ)-$(VER)/
	rm -rf ipf ipf.zip
	$(ZIP) $(PROJ)-$(VER)-win.zip $(PROJ)-$(VER)
