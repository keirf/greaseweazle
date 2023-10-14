
include Rules.mk

TARGETS := version install uninstall clean dist windist mypy
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
	rm -rf build dist .mypy_cache src/greaseweazle/__init__.py
	rm -rf src/*.egg-info src/greaseweazle/optimised/*.so
	rm -rf $(PROJ)-*
	find . -name __pycache__ | xargs rm -rf

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
	cd scripts/win && $(PYTHON) setup.py build
	cp -a scripts/win/build/exe.win*/* $(PROJ)-$(VER)/

# mypy testing
src/greaseweazle/__init__.py:
	echo "__version__: str" >$@
mypy: src/greaseweazle/__init__.py
	$(PYTHON) -m mypy --config-file=scripts/tests/mypy.ini
