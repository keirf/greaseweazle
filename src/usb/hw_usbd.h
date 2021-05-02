/*
 * hw_usbd.h
 * 
 * USB register definitions for STM32F10x USBD peripheral.
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

struct usb {
    uint32_t epr[8];   /* 4*n: Endpoint n */
    uint32_t rsvd[8];
    uint32_t cntr;     /* 40: Control */
    uint32_t istr;     /* 44: Interrupt status */
    uint32_t fnr;      /* 48: Frame number */
    uint32_t daddr;    /* 4C: Device address */
    uint32_t btable;   /* 50: Buffer table address */
};

struct usb_bufd {
    union {
        struct {
            uint32_t addr_tx;  /* 00: Transmission buffer address */
            uint32_t count_tx; /* 04: Transmission byte count */
            uint32_t addr_rx;  /* 08: Reception buffer address */
            uint32_t count_rx; /* 0C: Reception byte count */
        };
        struct {
            uint32_t addr_0;  /* 00: Double buffer #0 address */
            uint32_t count_0; /* 04: Double buffer #0 byte count */
            uint32_t addr_1;  /* 08: Double buffer #1 address */
            uint32_t count_1; /* 0C: Double buffer #1 byte count */
        };
    };
};

#define USB_EPR_CTR_RX       (1u<<15)
#define USB_EPR_DTOG_RX      (1u<<14)
#define USB_EPR_STAT_RX(x)   ((x)<<12)
#define USB_EPR_SETUP        (1u<<11)
#define USB_EPR_EP_TYPE(x)   ((x)<<9)
#define USB_EPR_EP_KIND_DBL_BUF (1<<8)    /* USB_EP_TYPE_BULK */
#define USB_EPR_EP_KIND_STATUS_OUT (1<<8) /* USB_EP_TYPE_CONTROL */
#define USB_EPR_CTR_TX       (1u<< 7)
#define USB_EPR_DTOG_TX      (1u<< 6)
#define USB_EPR_STAT_TX(x)   ((x)<<4)
#define USB_EPR_EA(x)        ((x)<<0)

#define USB_STAT_DISABLED    (0u)
#define USB_STAT_STALL       (1u)
#define USB_STAT_NAK         (2u)
#define USB_STAT_VALID       (3u)
#define USB_STAT_MASK        (3u)

#define USB_EP_TYPE_BULK     (0u)
#define USB_EP_TYPE_CONTROL  (1u)
#define USB_EP_TYPE_ISO      (2u)
#define USB_EP_TYPE_INTERRUPT (3u)
#define USB_EP_TYPE_MASK     (3u)

#define USB_CNTR_CTRM        (1u<<15)
#define USB_CNTR_PMAOVRM     (1u<<14)
#define USB_CNTR_ERRM        (1u<<13)
#define USB_CNTR_WKUPM       (1u<<12)
#define USB_CNTR_SUSPM       (1u<<11)
#define USB_CNTR_RESETM      (1u<<10)
#define USB_CNTR_SOFM        (1u<< 9)
#define USB_CNTR_ESOFM       (1u<< 8)
#define USB_CNTR_RESUME      (1u<< 4)
#define USB_CNTR_FSUSP       (1u<< 3)
#define USB_CNTR_LP_MODE     (1u<< 2)
#define USB_CNTR_PDWN        (1u<< 1)
#define USB_CNTR_FRES        (1u<< 0)

#define USB_ISTR_CTR         (1u<<15)
#define USB_ISTR_PMAOVR      (1u<<14)
#define USB_ISTR_ERR         (1u<<13)
#define USB_ISTR_WKUP        (1u<<12)
#define USB_ISTR_SUSP        (1u<<11)
#define USB_ISTR_RESET       (1u<<10)
#define USB_ISTR_SOF         (1u<< 9)
#define USB_ISTR_ESOF        (1u<< 8)
#define USB_ISTR_DIR         (1u<< 4)
#define USB_ISTR_GET_EP_ID(x) ((x)&0xf)

#define USB_FNR_RXDP         (1u<<15)
#define USB_FNR_RXDM         (1u<<14)
#define USB_FNR_LCK          (1u<<13)
#define USB_FNR_GET_LSOF(x)  (((x)>>11)&3)
#define USB_FNR_GET_FN(x)    ((x)&0x7ff)

#define USB_DADDR_EF         (1u<< 7)
#define USB_DADDR_ADD(x)     ((x)<<0)

/* C pointer types */
#define USB volatile struct usb * const
#define USB_BUFD volatile struct usb_bufd * const
#define USB_BUF volatile uint32_t * const

/* C-accessible registers. */
static USB usb = (struct usb *)USB_BASE;
static USB_BUFD usb_bufd = (struct usb_bufd *)USB_BUF_BASE;
static USB_BUF usb_buf = (uint32_t *)USB_BUF_BASE;

/*
 * Local variables:
 * mode: C
 * c-file-style: "Linux"
 * c-basic-offset: 4
 * tab-width: 4
 * indent-tabs-mode: nil
 * End:
 */
