
export FW_VER := 0.1

PROJ = Greaseweazle
VER := v$(FW_VER)

SUBDIRS += src

.PHONY: all clean dist mrproper flash start serial

ifneq ($(RULES_MK),y)
export ROOT := $(CURDIR)
all:
	$(MAKE) -C src -f $(ROOT)/Rules.mk $(PROJ).elf $(PROJ).bin $(PROJ).hex
	cp -a src/$(PROJ).hex $(PROJ)-$(VER).hex

clean:
	$(MAKE) -f $(ROOT)/Rules.mk $@

dist:
	rm -rf $(PROJ)-*
	mkdir -p $(PROJ)-$(VER)/scripts
	$(MAKE) clean
	$(MAKE) all
	cp -a $(PROJ)-$(VER).hex $(PROJ)-$(VER)/
	$(MAKE) clean
	cp -a COPYING $(PROJ)-$(VER)/
	cp -a README.md $(PROJ)-$(VER)/
	cp -a scripts/49-greaseweazle.rules $(PROJ)-$(VER)/scripts/.
	cp -a scripts/gw.py $(PROJ)-$(VER)/
#	cp -a RELEASE_NOTES $(PROJ)-$(VER)/
	zip -r $(PROJ)-$(VER).zip $(PROJ)-$(VER)

mrproper: clean
	rm -rf $(PROJ)-*

endif

BAUD=115200
DEV=/dev/ttyUSB0

flash: all
	sudo stm32flash -b $(BAUD) -w src/$(PROJ).hex $(DEV)

start:
	sudo stm32flash -b $(BAUD) -g 0 $(DEV)

serial:
	sudo miniterm.py $(DEV) 3000000
