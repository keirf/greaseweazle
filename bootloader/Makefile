RPATH = ../src

OBJS += board.o
OBJS += build_info.o
OBJS += crc.o
OBJS += vectors.o
OBJS += fw_update.o
OBJS += string.o
OBJS += stm32f10x.o
OBJS += util.o
OBJS += fpec.o

OBJS-$(debug) += console.o

SUBDIRS += usb

.PHONY: $(RPATH)/build_info.c
build_info.o: CFLAGS += -DFW_MAJOR=$(FW_MAJOR) -DFW_MINOR=$(FW_MINOR)
