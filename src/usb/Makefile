OBJS += config.o
OBJS += core.o
OBJS += cdc_acm.o
OBJS-$(stm32f1) += hw_f1.o
OBJS-$(stm32f7) += hw_dwc_otg.o

$(OBJS) $(OBJS-y): CFLAGS += -include defs.h
