
PROJ = Greaseweazle
VER = v0.0.1a

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
	rm -rf $(PROJ)_*
	mkdir -p $(PROJ)_$(VER)/reloader
	$(MAKE) clean
	$(MAKE) all
	cp -a $(PROJ)-$(VER).hex $(PROJ)_$(VER)/
	$(MAKE) clean
	cp -a COPYING $(PROJ)_$(VER)/
	cp -a README.md $(PROJ)_$(VER)/
#	cp -a RELEASE_NOTES $(PROJ)_$(VER)/
	zip -r $(PROJ)_$(VER).zip $(PROJ)_$(VER)

mrproper: clean
	rm -rf $(PROJ)_*

endif

BAUD=115200
DEV=/dev/ttyUSB0

flash: all
	sudo stm32flash -b $(BAUD) -w src/$(PROJ).hex $(DEV)

start:
	sudo stm32flash -b $(BAUD) -g 0 $(DEV)

serial:
	sudo miniterm.py $(DEV) 3000000
