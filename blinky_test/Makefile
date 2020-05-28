RPATH = $(ROOT)/src

OBJS += vectors.o
OBJS += cortex.o
OBJS += blinky.o
OBJS += util.o
OBJS += console.o
OBJS += string.o

SUBDIRS += $(stm32)

console.o: CFLAGS += -DBAUD=115200
