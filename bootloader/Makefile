RPATH = $(ROOT)/src

OBJS += board.o
OBJS += build_info.o
OBJS += crc.o
OBJS += vectors.o
OBJS += fw_update.o
OBJS += string.o
OBJS += cortex.o
OBJS += time.o
OBJS += timer.o
OBJS += util.o

OBJS-$(debug) += console.o

SUBDIRS += usb
SUBDIRS-$(stm32f1) += f1
SUBDIRS-$(stm32f7) += f7

.PHONY: $(RPATH)/build_info.c
build_info.o: CFLAGS += -DFW_MAJOR=$(FW_MAJOR) -DFW_MINOR=$(FW_MINOR)
