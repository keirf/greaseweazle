OBJS += board.o
OBJS += build_info.o
OBJS += crc.o
OBJS += vectors.o
OBJS += main.o
OBJS += string.o
OBJS += cortex.o
OBJS += time.o
OBJS += timer.o
OBJS += util.o
OBJS += floppy.o

OBJS-$(debug) += console.o

SUBDIRS += mcu usb

.PHONY: build_info.c
build_info.o: CFLAGS += -DFW_MAJOR=$(FW_MAJOR) -DFW_MINOR=$(FW_MINOR)
