OBJS += board.o
OBJS += build_info.o
OBJS += vectors.o
OBJS += main.o
OBJS += string.o
OBJS += cortex.o
OBJS += stm32$(stm32).o
OBJS += time.o
OBJS += timer.o
OBJS += util.o
OBJS += floppy.o

OBJS-$(debug) += console.o

SUBDIRS += usb

.PHONY: build_info.c
build_info.o: CFLAGS += -DFW_MAJOR=$(FW_MAJOR) -DFW_MINOR=$(FW_MINOR)
