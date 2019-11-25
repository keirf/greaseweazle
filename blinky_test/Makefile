RPATH = ../src

OBJS += vectors.o
OBJS += cortex.o
OBJS += stm32$(stm32).o
OBJS += blinky.o
OBJS += util.o
OBJS += fpec.o
OBJS += console.o
OBJS += string.o

console.o: CFLAGS += -DBAUD=115200
