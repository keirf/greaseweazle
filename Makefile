
export FW_MAJOR := 0
export FW_MINOR := 33

TARGETS := all blinky clean dist windist mrproper f1_ocd ocd flash start serial pysetup
.PHONY: $(TARGETS)

ifneq ($(RULES_MK),y)

export ROOT := $(CURDIR)

$(TARGETS):
	$(MAKE) -f $(ROOT)/Rules.mk $@

else

PROJ = Greaseweazle
VER := v$(FW_MAJOR).$(FW_MINOR)

SUBDIRS += src bootloader blinky_test

all: scripts/greaseweazle/version.py
	$(MAKE) -C src -f $(ROOT)/Rules.mk $(PROJ).elf $(PROJ).bin $(PROJ).hex
	$(MAKE) bootloader=y -C bootloader -f $(ROOT)/Rules.mk \
		Bootloader.elf Bootloader.bin Bootloader.hex
	srec_cat bootloader/Bootloader.hex -Intel src/$(PROJ).hex -Intel \
	-o $(PROJ)-$(VER).hex -Intel
	$(PYTHON) ./scripts/mk_update.py new $(PROJ)-$(VER).upd \
		bootloader/Bootloader.bin src/$(PROJ).bin $(mcu)

blinky:
	$(MAKE) debug=y mcu=stm32f1 -C blinky_test -f $(ROOT)/Rules.mk \
		Blinky.elf Blinky.bin Blinky.hex

clean::
	rm -rf scripts/greaseweazle/optimised/optimised* scripts/c_ext/build
	rm -f *.hex *.upd scripts/greaseweazle/*.pyc
	rm -f scripts/greaseweazle/version.py
	find . -name __pycache__ | xargs rm -rf

dist:
	rm -rf $(PROJ)-*
	mkdir -p $(PROJ)-$(VER)/scripts/greaseweazle/image
	mkdir -p $(PROJ)-$(VER)/scripts/greaseweazle/tools
	mkdir -p $(PROJ)-$(VER)/scripts/misc
	mkdir -p $(PROJ)-$(VER)/hex/alt
	$(MAKE) clean
	$(MAKE) mcu=stm32f1 all blinky
	cp -a $(PROJ)-$(VER).hex $(PROJ)-$(VER)/hex/$(PROJ)-F1-$(VER).hex
	cp -a $(PROJ)-$(VER).upd $(PROJ)-$(VER)/$(PROJ)-$(VER).upd
	cp -a blinky_test/Blinky.hex $(PROJ)-$(VER)/hex/alt/Blinky_Test-F1-$(VER).hex
	cp -a COPYING $(PROJ)-$(VER)/
	cp -a README.md $(PROJ)-$(VER)/
	cp -a gw $(PROJ)-$(VER)/
	cp -a scripts/49-greaseweazle.rules $(PROJ)-$(VER)/scripts/
	cp -a scripts/setup.sh $(PROJ)-$(VER)/scripts/
	cp -a scripts/gw.py $(PROJ)-$(VER)/scripts/
	cp -a scripts/greaseweazle $(PROJ)-$(VER)/scripts
	cp -a scripts/c_ext $(PROJ)-$(VER)/scripts
	cp -a scripts/misc/*.py $(PROJ)-$(VER)/scripts/misc/
	cp -a RELEASE_NOTES $(PROJ)-$(VER)/
	$(MAKE) clean
	$(MAKE) mcu=stm32f7 all
	cp -a $(PROJ)-$(VER).hex $(PROJ)-$(VER)/hex/$(PROJ)-F7-$(VER).hex
	$(PYTHON) ./scripts/mk_update.py cat $(PROJ)-$(VER)/$(PROJ)-$(VER).upd \
		$(PROJ)-$(VER)/$(PROJ)-$(VER).upd $(PROJ)-$(VER).upd
	$(MAKE) clean
	$(MAKE) mcu=at32f4 all
	cp -a $(PROJ)-$(VER).hex $(PROJ)-$(VER)/hex/$(PROJ)-AT32F4-$(VER).hex
	$(PYTHON) ./scripts/mk_update.py cat $(PROJ)-$(VER)/$(PROJ)-$(VER).upd \
		$(PROJ)-$(VER)/$(PROJ)-$(VER).upd $(PROJ)-$(VER).upd
	$(MAKE) clean
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

BAUD=115200
DEV=/dev/ttyUSB0

ocd: all
	$(PYTHON) scripts/telnet.py localhost 4444 \
	"reset init ; flash write_image erase `pwd`/$(PROJ)-$(VER).hex ; reset"

f1_ocd: all
	python3 scripts/openocd/flash.py `pwd`/$(PROJ)-$(VER).hex

flash: all
	sudo stm32flash -b $(BAUD) -w $(PROJ)-$(VER).hex $(DEV)

start:
	sudo stm32flash -b $(BAUD) -g 0 $(DEV)

serial:
	sudo miniterm.py $(DEV) 3000000

endif
