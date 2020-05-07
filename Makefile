
export FW_MAJOR := 0
export FW_MINOR := 15

TARGETS := all blinky clean dist mrproper ocd flash start serial
.PHONY: $(TARGETS)

ifneq ($(RULES_MK),y)

export ROOT := $(CURDIR)
export stm32
export debug
export VERBOSE

$(TARGETS):
	$(MAKE) -f $(ROOT)/Rules.mk $@

else

PROJ = Greaseweazle
VER := v$(FW_MAJOR).$(FW_MINOR)

SUBDIRS += src bootloader blinky_test

all: scripts/greaseweazle/version.py
	$(MAKE) -C src -f $(ROOT)/Rules.mk $(PROJ).elf $(PROJ).bin $(PROJ).hex
	bootloader=y $(MAKE) -C bootloader -f $(ROOT)/Rules.mk \
		Bootloader.elf Bootloader.bin Bootloader.hex
	srec_cat bootloader/Bootloader.hex -Intel src/$(PROJ).hex -Intel \
	-o $(PROJ)-$(VER).hex -Intel
	$(PYTHON) ./scripts/mk_update.py src/$(PROJ).bin $(PROJ)-$(VER).upd $(stm32)

blinky:
	debug=y stm32=f1 $(MAKE) -C blinky_test -f $(ROOT)/Rules.mk \
		Blinky.elf Blinky.bin Blinky.hex

clean::
	rm -f *.hex *.upd scripts/greaseweazle/*.pyc
	rm -f scripts/greaseweazle/version.py
	find . -name __pycache__ | xargs rm -rf

dist:
	rm -rf $(PROJ)-*
	mkdir -p $(PROJ)-$(VER)/scripts/greaseweazle/image
	mkdir -p $(PROJ)-$(VER)/scripts/greaseweazle/tools
	mkdir -p $(PROJ)-$(VER)/alt
	$(MAKE) clean
	stm32=f1 $(MAKE) all blinky
	cp -a $(PROJ)-$(VER).hex $(PROJ)-$(VER)/$(PROJ)-F1-$(VER).hex
	cp -a $(PROJ)-$(VER).upd $(PROJ)-$(VER)/$(PROJ)-$(VER).upd
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
	stm32=f7 $(MAKE) all
	cp -a $(PROJ)-$(VER).hex $(PROJ)-$(VER)/$(PROJ)-F7-$(VER).hex
	cat $(PROJ)-$(VER).upd >>$(PROJ)-$(VER)/$(PROJ)-$(VER).upd
	$(MAKE) clean
	$(ZIP) $(PROJ)-$(VER).zip $(PROJ)-$(VER)

mrproper: clean
	rm -rf $(PROJ)-*

scripts/greaseweazle/version.py: Makefile
	echo "major = $(FW_MAJOR)" >$@
	echo "minor = $(FW_MINOR)" >>$@

BAUD=115200
DEV=/dev/ttyUSB0

ocd: all
	$(PYTHON) scripts/telnet.py localhost 4444 \
	"reset init ; flash write_image erase `pwd`/$(PROJ)-$(VER).hex ; reset"

flash: all
	sudo stm32flash -b $(BAUD) -w $(PROJ)-$(VER).hex $(DEV)

start:
	sudo stm32flash -b $(BAUD) -g 0 $(DEV)

serial:
	sudo miniterm.py $(DEV) 3000000

endif
