
export FW_MAJOR := 0
export FW_MINOR := 6

PROJ = Greaseweazle
VER := v$(FW_MAJOR).$(FW_MINOR)

SUBDIRS += src bootloader blinky_test

.PHONY: all clean dist mrproper flash start serial

ifneq ($(RULES_MK),y)
export ROOT := $(CURDIR)

all:
	$(MAKE) -f $(ROOT)/Rules.mk $@

clean:
	rm -f *.hex *.upd scripts/greaseweazle/*.pyc
	rm -f scripts/greaseweazle/version.py
	find . -name __pycache__ | xargs rm -rf
	$(MAKE) -f $(ROOT)/Rules.mk $@

dist:
	rm -rf $(PROJ)-*
	mkdir -p $(PROJ)-$(VER)/scripts/greaseweazle/image
	mkdir -p $(PROJ)-$(VER)/scripts/greaseweazle/tools
	mkdir -p $(PROJ)-$(VER)/alt
	$(MAKE) clean
	$(MAKE) all
	cp -a $(PROJ)-$(VER).hex $(PROJ)-$(VER)/
	cp -a $(PROJ)-$(VER).upd $(PROJ)-$(VER)/
	cp -a blinky_test/Blinky.hex $(PROJ)-$(VER)/alt/Blinky_Test-$(VER).hex
	cp -a COPYING $(PROJ)-$(VER)/
	cp -a README.md $(PROJ)-$(VER)/
	cp -a gw.py $(PROJ)-$(VER)/
	cp -a scripts/49-greaseweazle.rules $(PROJ)-$(VER)/scripts/
	cp -a scripts/gw.py $(PROJ)-$(VER)/scripts/
	cp -a scripts/greaseweazle/*.py $(PROJ)-$(VER)/scripts/greaseweazle/
	cp -a scripts/greaseweazle/image/*.py \
		$(PROJ)-$(VER)/scripts/greaseweazle/image/
	cp -a scripts/greaseweazle/tools/*.py \
		$(PROJ)-$(VER)/scripts/greaseweazle/tools/
	cp -a RELEASE_NOTES $(PROJ)-$(VER)/
	$(MAKE) clean
	zip -r $(PROJ)-$(VER).zip $(PROJ)-$(VER)

mrproper: clean
	rm -rf $(PROJ)-*

else

all: scripts/greaseweazle/version.py
	$(MAKE) -C src -f $(ROOT)/Rules.mk $(PROJ).elf $(PROJ).bin $(PROJ).hex
	bootloader=y $(MAKE) -C bootloader -f $(ROOT)/Rules.mk \
		Bootloader.elf Bootloader.bin Bootloader.hex
	debug=y $(MAKE) -C blinky_test -f $(ROOT)/Rules.mk \
		Blinky.elf Blinky.bin Blinky.hex
	srec_cat bootloader/Bootloader.hex -Intel src/$(PROJ).hex -Intel \
	-o $(PROJ)-$(VER).hex -Intel
	$(PYTHON) ./scripts/mk_update.py src/$(PROJ).bin $(PROJ)-$(VER).upd

scripts/greaseweazle/version.py: Makefile
	echo "major = $(FW_MAJOR)" >$@
	echo "minor = $(FW_MINOR)" >>$@

endif

BAUD=115200
DEV=/dev/ttyUSB0

flash: all
	sudo stm32flash -b $(BAUD) -w $(PROJ)-$(VER).hex $(DEV)

start:
	sudo stm32flash -b $(BAUD) -g 0 $(DEV)

serial:
	sudo miniterm.py $(DEV) 3000000
