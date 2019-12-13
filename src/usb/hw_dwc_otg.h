/*
 * hw_dwc_otg.h
 * 
 * USB register definitions for DWC-OTG USB 2.0 controller.
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

#define PORT_FS 0
#define PORT_HS 1

#define IFACE_FS 0
#define IFACE_HS_EMBEDDED 1
#define IFACE_HS_ULPI     2

#define conf_port PORT_HS
#define conf_iface IFACE_FS
#define conf_nr_ep 4

/* USB On-The-Go Full Speed interface */
struct otg {
    /* GLOBAL */
    uint32_t gotgctl;  /* 00: Control and status */
    uint32_t gotgint;  /* 04: Interrupt */
    uint32_t gahbcfg;  /* 08: AHB configuration */
    uint32_t gusbcfg;  /* 0C: USB configuration */
    uint32_t grstctl;  /* 10: Reset */
    uint32_t gintsts;  /* 14: Core interrupt */
    uint32_t gintmsk;  /* 18: Interrupt mask */
    uint32_t grxstsr;  /* 1C: Receive status debug read */
    uint32_t grxstsp;  /* 20: Receive status read & pop */
    uint32_t grxfsiz;  /* 24: Receive FIFO size */
    union {
        uint32_t hnptxfsiz;  /* 28: Host non-periodic transmit FIFO size */
        uint32_t dieptxf0;   /* 28: Endpoint 0 transmit FIFO size */
    };
    uint32_t hnptxsts; /* 2C: Non-periodic transmit FIFO/queue status */
    uint32_t _0[2];
    uint32_t gccfg;    /* 38: General core configuration */
    uint32_t cid;      /* 3C: Core ID */
    uint32_t _1[48];
    uint32_t hptxfsiz; /* 100: Host periodic transmit FIFO size */
    uint32_t dieptxf[15]; /* 104: Device IN endpoint transmit FIFO sizes */
};

struct otgh {
    /* HOST */
    uint32_t hcfg;     /* 400: Host configuration */
    uint32_t hfir;     /* 404: Host frame interval */
    uint32_t hfnum;    /* 408: Host frame number / frame time remaining */
    uint32_t _3[1];    /* 40C: */
    uint32_t hptxsts;  /* 410: Host periodic transmit FIFO / queue status */
    uint32_t haint;    /* 414: Host all channels interrupt status */
    uint32_t haintmsk; /* 418: Host all channels interrupt mask */
    uint32_t _4[9];
    uint32_t hprt;     /* 440: Host port control and status */
    uint32_t _5[47];
    struct {
        uint32_t charac; /* +00: Host channel-x characteristics */
        uint32_t _0[1];
        uint32_t intsts; /* +08: Host channel-x interrupt status */
        uint32_t intmsk; /* +0C: Host channel-x interrupt mask */
        uint32_t tsiz;   /* +10: Host channel x transfer size */
        uint32_t _1[3];
    } hc[8];           /* 500..5E0: */
};

struct otgd {
    /* DEVICE */
    uint32_t dcfg;     /* 800: Device configuration */
    uint32_t dctl;     /* 804: Device control */
    uint32_t dsts;     /* 808: Device status */
    uint32_t _7[1];
    uint32_t diepmsk;  /* 810: Device IN endpoint common interrupt mask */
    uint32_t doepmsk;  /* 814: Device OUT endpoint common interrupt mask */
    uint32_t daint;    /* 818: Device all endpoints interrupt status */
    uint32_t daintmsk; /* 81C: Device all endpoints interrupt mask */
    uint32_t _8[2];
    uint32_t dvbusdis; /* 828: Device VBUS discharge time */
    uint32_t dvbuspulse; /* 82C: Device VBUS pulsing time */
    uint32_t _9[1];
    uint32_t diepempmsk; /* 834: Device IN endpoint FIFO empty int. mask */
};

struct otg_diep { /* 900.. */
    /* DEVICE IN */
    uint32_t ctl;    /* +00: Device IN endpoint-x control */
    uint32_t _0[1];
    uint32_t intsts; /* +08: Device IN endpoint-x interrupt status */
    uint32_t _1[1];
    uint32_t tsiz;   /* +10: Device IN endpoint-x transfer size */
    uint32_t dma;    /* +14: Device IN endpoint-x DMA address */
    uint32_t txfsts; /* +18: Device IN endpoint-x transmit FIFO status */
    uint32_t _3[1];
};

struct otg_doep { /* B00.. */
    /* DEVICE OUT */
    uint32_t ctl;    /* +00: Device OUT endpoint-x control */
    uint32_t _0[1];
    uint32_t intsts; /* +08: Device OUT endpoint-x interrupt status */
    uint32_t _1[1];
    uint32_t tsiz;   /* +10: Device OUT endpoint-x transmit FIFO status */
    uint32_t dma;    /* +14: Device OUT endpoint-x DMA address */
    uint32_t _2[2];
};

struct otg_pcgcctl {
    uint32_t pcgcctl;  /* E00: Power and clock gating control */
};

struct otg_dfifo { /* 1000.. */
    uint32_t x[0x1000/4];
};

#define OTG_GOTGCTL_CURMOD   (1u<<21)
#define OTG_GOTGCTL_OTGVER   (1u<<20)
#define OTG_GOTGCTL_BSVLD    (1u<<19)
#define OTG_GOTGCTL_ASVLD    (1u<<18)
#define OTG_GOTGCTL_DBCT     (1u<<17)
#define OTG_GOTGCTL_CIDSTS   (1u<<16)
#define OTG_GOTGCTL_EHEN     (1u<<12)
#define OTG_GOTGCTL_DHNPEN   (1u<<11)
#define OTG_GOTGCTL_HSHNPEN  (1u<<10)
#define OTG_GOTGCTL_HNPRQ    (1u<< 9)
#define OTG_GOTGCTL_HNGSCS   (1u<< 8)
#define OTG_GOTGCTL_BVALOVAL (1u<< 7)
#define OTG_GOTGCTL_BVALOEN  (1u<< 6)
#define OTG_GOTGCTL_AVALOVAL (1u<< 5)
#define OTG_GOTGCTL_AVALOEN  (1u<< 4)
#define OTG_GOTGCTL_VBVALOVAL (1u<< 3)
#define OTG_GOTGCTL_VBVALOEN (1u<< 2)
#define OTG_GOTGCTL_SRQ      (1u<< 1)
#define OTG_GOTGCTL_SRQSCS   (1u<< 0)

#define OTG_GAHBCFG_PTXFELVL (1u<< 8)
#define OTG_GAHBCFG_TXFELVL  (1u<< 7)
#define OTG_GAHBCFG_GINTMSK  (1u<< 0)

#define OTG_GUSBCFG_CTXPKT   (1u<<31)
#define OTG_GUSBCFG_FDMOD    (1u<<30)
#define OTG_GUSBCFG_FHMOD    (1u<<29)
#define OTG_GUSBCFG_ULPIIPD  (1u<<25)
#define OTG_GUSBCFG_PTCI     (1u<<24)
#define OTG_GUSBCFG_PCCI     (1u<<23)
#define OTG_GUSBCFG_TSDPS    (1u<<22)
#define OTG_GUSBCFG_ULPIEVBUSI (1u<<21)
#define OTG_GUSBCFG_ULPIEVBUSD (1u<<20)
#define OTG_GUSBCFG_ULPICSM  (1u<<19)
#define OTG_GUSBCFG_ULPIAR   (1u<<18)
#define OTG_GUSBCFG_ULPIFSL  (1u<<17)
#define OTG_GUSBCFG_PHYLPC   (1u<<15)
#define OTG_GUSBCFG_TRDT(x)  ((x)<<10)
#define OTG_GUSBCFG_HNPCAP   (1u<< 9)
#define OTG_GUSBCFG_SRPCAP   (1u<< 8)
#define OTG_GUSBCFG_PHYSEL   (1u<< 6)
#define OTG_GUSBCFG_ULPISEL  (1u<< 4)
#define OTG_GUSBCFG_TOCAL(x) ((x)<< 0)

#define OTG_GRSTCTL_AHBIDL   (1u<<31)
#define OTG_GRSTCTL_DMAREQ   (1u<<30)
#define OTG_GRSTCTL_TXFNUM(x) ((x)<<6)
#define OTG_GRSTCTL_TXFFLSH  (1u<< 5)
#define OTG_GRSTCTL_RXFFLSH  (1u<< 4)
#define OTG_GRSTCTL_PSRST    (1u<< 1)
#define OTG_GRSTCTL_CSRST    (1u<< 0)

/* GINTSTS and GINTMSK */
#define OTG_GINT_WKUPINT     (1u<<31) /* Host + Device */
#define OTG_GINT_SRQINT      (1u<<30) /* H + D */
#define OTG_GINT_DISCINT     (1u<<29) /* H */
#define OTG_GINT_CIDSCHG     (1u<<28) /* H + D */
#define OTG_GINT_PTXFE       (1u<<26) /* H */
#define OTG_GINT_HCINT       (1u<<25) /* H */
#define OTG_GINT_HPRTINT     (1u<<24) /* H */
#define OTG_GINT_IPXFR       (1u<<21) /* H */
#define OTG_GINT_IISOIXFR    (1u<<20) /* D */
#define OTG_GINT_OEPINT      (1u<<19) /* D */
#define OTG_GINT_IEPINT      (1u<<18) /* D */
#define OTG_GINT_EOPF        (1u<<15) /* D */
#define OTG_GINT_ISOODRP     (1u<<14) /* D */
#define OTG_GINT_ENUMDNE     (1u<<13) /* D */
#define OTG_GINT_USBRST      (1u<<12) /* D */
#define OTG_GINT_USBSUSP     (1u<<11) /* D */
#define OTG_GINT_ESUSP       (1u<<10) /* D */
#define OTG_GINT_GONAKEFF    (1u<< 7) /* D */
#define OTG_GINT_GINAKEFF    (1u<< 6) /* D */
#define OTG_GINT_NPTXFE      (1u<< 5) /* H */
#define OTG_GINT_RXFLVL      (1u<< 4) /* H + D */
#define OTG_GINT_SOF         (1u<< 3) /* H + D */
#define OTG_GINT_OTGINT      (1u<< 2) /* H + D */
#define OTG_GINT_MMIS        (1u<< 1) /* H + D */
#define OTG_GINT_CMOD        (1u<< 0) /* H + D */

#define STS_GOUT_NAK                           1U
#define STS_DATA_UPDT                          2U
#define STS_XFER_COMP                          3U
#define STS_SETUP_COMP                         4U
#define STS_SETUP_UPDT                         6U
#define OTG_RXSTS_PKTSTS(r)  (((r)>>17)&0xf)
#define OTG_RXSTS_BCNT(r)    (((r)>>4)&0x7ff)
#define OTG_RXSTS_CHNUM(r)   ((r)&0xf)

#define OTG_GCCFG_PHYHSEN    (1u<<23)
#define OTG_GCCFG_VBDEN      (1u<<21)
#define OTG_GCCFG_PWRDWN     (1u<<16)

#define OTG_HCFG_FSLSS       (1u<<2)
#define OTG_HCFG_FSLSPCS     (3u<<0)
#define OTG_HCFG_FSLSPCS_48  (1u<<0)
#define OTG_HCFG_FSLSPCS_6   (2u<<0)

#define OTG_HPRT_PSPD_FULL   (1u<<17)
#define OTG_HPRT_PSPD_LOW    (2u<<17)
#define OTG_HPRT_PSPD_MASK   (1u<<17) /* read-only */
#define OTG_HPRT_PPWR        (1u<<12)
#define OTG_HPRT_PRST        (1u<< 8)
#define OTG_HPRT_PSUSP       (1u<< 7)
#define OTG_HPRT_PRES        (1u<< 6)
#define OTG_HPRT_POCCHNG     (1u<< 5) /* raises HPRTINT */
#define OTG_HPRT_POCA        (1u<< 4)
#define OTG_HPRT_PENCHNG     (1u<< 3) /* raises HPRTINT */
#define OTG_HPRT_PENA        (1u<< 2)
#define OTG_HPRT_PCDET       (1u<< 1) /* raises HPRTINT */
#define OTG_HPRT_PCSTS       (1u<< 0)
#define OTG_HPRT_INTS (OTG_HPRT_POCCHNG|OTG_HPRT_PENCHNG|OTG_HPRT_PCDET| \
                       OTG_HPRT_PENA) /* PENA is also set-to-clear  */

/* HCINTSTS and HCINTMSK */
#define OTG_HCINT_DTERR      (1u<<10)
#define OTG_HCINT_FRMOR      (1u<< 9)
#define OTG_HCINT_BBERR      (1u<< 8)
#define OTG_HCINT_TXERR      (1u<< 7)
#define OTG_HCINT_NYET       (1u<< 6) /* high-speed only; not STM32F10x */
#define OTG_HCINT_ACK        (1u<< 5)
#define OTG_HCINT_NAK        (1u<< 4)
#define OTG_HCINT_STALL      (1u<< 3)
#define OTG_HCINT_CHH        (1u<< 1)
#define OTG_HCINT_XFRC       (1u<< 0)

#define OTG_HCCHAR_CHENA     (1u<<31)
#define OTG_HCCHAR_CHDIS     (1u<<30)
#define OTG_HCCHAR_ODDFRM    (1u<<29)
#define OTG_HCCHAR_DAD(x)    ((x)<<22)
#define OTG_HCCHAR_MCNT(x)   ((x)<<20)
#define OTG_HCCHAR_ETYP_CTRL (0u<<18)
#define OTG_HCCHAR_ETYP_ISO  (1u<<18)
#define OTG_HCCHAR_ETYP_BULK (2u<<18)
#define OTG_HCCHAR_ETYP_INT  (3u<<18)
#define OTG_HCCHAR_LSDEV     (1u<<17)
#define OTG_HCCHAR_EPDIR_OUT (0u<<15)
#define OTG_HCCHAR_EPDIR_IN  (1u<<15)
#define OTG_HCCHAR_EPNUM(x)  ((x)<<11)
#define OTG_HCCHAR_MPSIZ(x)  ((x)<< 0)

#define OTG_HCTSIZ_DPID_DATA0 (0u<<29)
#define OTG_HCTSIZ_DPID_DATA2 (1u<<29)
#define OTG_HCTSIZ_DPID_DATA1 (2u<<29)
#define OTG_HCTSIZ_DPID_MDATA (3u<<29)
#define OTG_HCTSIZ_DPID_SETUP (3u<<29)
#define OTG_HCTSIZ_PKTCNT(x)  ((x)<<19)
#define OTG_HCTSIZ_XFRSIZ(x)  ((x)<< 0)

#define OTG_DCFG_PERSCHIVL(x) ((x)<<24)
#define OTG_DCFG_ERRATIM      (1u<<15)
#define OTG_DCFG_XCVRDLY      (1u<<14)
#define OTG_DCFG_PFIVL(x)     ((x)<<11)
#define OTG_DCFG_DAD(x)       ((x)<<4)
#define OTG_DCFG_NZLSOHSK     (1u<< 2)
#define OTG_DCFG_DSPD(x)      ((x)<<0)

#define OTG_DCTL_DSBESLRJCT   (1u<<18)
#define OTG_DCTL_POPRGDNE     (1u<<11)
#define OTG_DCTL_CGONAK       (1u<<10)
#define OTG_DCTL_SGONAK       (1u<< 9)
#define OTG_DCTL_CGINAK       (1u<< 8)
#define OTG_DCTL_SGINAK       (1u<< 7)
#define OTG_DCTL_GONSTS       (1u<< 3)
#define OTG_DCTL_GINSTS       (1u<< 2)
#define OTG_DCTL_SDIS         (1u<< 1)
#define OTG_DCTL_RWUSIG       (1u<< 0)

#define OTG_DIEPMSK_NAKM      (1u<<13)
#define OTG_DIEPMSK_TXFURM    (1u<< 8)
#define OTG_DIEPMSK_INEPNEM   (1u<< 6)
#define OTG_DIEPMSK_INEPNMM   (1u<< 5)
#define OTG_DIEPMSK_ITTXFEMSK (1u<< 4)
#define OTG_DIEPMSK_TOM       (1u<< 3)
#define OTG_DIEPMSK_AHBERRM   (1u<< 2)
#define OTG_DIEPMSK_EPDM      (1u<< 1)
#define OTG_DIEPMSK_XFRCM     (1u<< 0)

#define OTG_DIEPINT_TXFE      (1u<< 7)
#define OTG_DIEPINT_XFRC      (1u<< 0)

#define OTG_DOEPMSK_NYETMSK   (1u<<14)
#define OTG_DOEPMSK_NAKM      (1u<<13)
#define OTG_DOEPMSK_BERRM     (1u<<12)
#define OTG_DOEPMSK_OUTPKTERRM (1u<< 8)
#define OTG_DOEPMSK_B2BSTUPM  (1u<< 6)
#define OTG_DOEPMSK_STSPHSRXM (1u<< 5)
#define OTG_DOEPMSK_OTEPDM    (1u<< 4)
#define OTG_DOEPMSK_STUPM     (1u<< 3)
#define OTG_DOEPMSK_AHBERRM   (1u<< 2)
#define OTG_DOEPMSK_EPDM      (1u<< 1)
#define OTG_DOEPMSK_XFRCM     (1u<< 0)

#define OTG_DIEPCTL_EPENA     (1u<<31)
#define OTG_DIEPCTL_EPDIS     (1u<<30)
#define OTG_DIEPCTL_SODDFRM   (1u<<29)
#define OTG_DIEPCTL_SD0PID    (1u<<28)
#define OTG_DIEPCTL_SNAK      (1u<<27)
#define OTG_DIEPCTL_CNAK      (1u<<26)
#define OTG_DIEPCTL_TXFNUM(x) ((x)<<22)
#define OTG_DIEPCTL_STALL     (1u<<21)
#define OTG_DIEPCTL_EPTYP(x)  ((x)<<18)
#define OTG_DIEPCTL_NAKSTS    (1u<<17)
#define OTG_DIEPCTL_DPID      (1u<<16)
#define OTG_DIEPCTL_USBAEP    (1u<<15)
#define OTG_DIEPCTL_MPSIZ(x)  ((x)<<0)

#define OTG_DIEPTSIZ_PKTCNT(x) ((x)<<19)
#define OTG_DIEPTSIZ_XFRSIZ(x) ((x)<<0)

#define OTG_DOEPCTL_EPENA     (1u<<31)
#define OTG_DOEPCTL_EPDIS     (1u<<30)
#define OTG_DOEPCTL_SD1PID    (1u<<29)
#define OTG_DOEPCTL_SD0PID    (1u<<28)
#define OTG_DOEPCTL_SNAK      (1u<<27)
#define OTG_DOEPCTL_CNAK      (1u<<26)
#define OTG_DOEPCTL_STALL     (1u<<21)
#define OTG_DOEPCTL_SNPM      (1u<<20)
#define OTG_DOEPCTL_EPTYP(x)  ((x)<<18)
#define OTG_DOEPCTL_NAKSTS    (1u<<17)
#define OTG_DOEPCTL_DPID      (1u<<16)
#define OTG_DOEPCTL_USBAEP    (1u<<15)
#define OTG_DOEPCTL_MPSIZ(x)  ((x)<<0)

#define OTG_DOEPTSZ_STUPCNT   (3u<<29)
#define OTG_DOEPTSZ_PKTCNT(x) ((x)<<19)
#define OTG_DOEPTSZ_XFERSIZ(x) ((x)<<0)

/* C pointer types */
#define OTG volatile struct otg * const
#define OTGH volatile struct otgh * const
#define OTGD volatile struct otgd * const
#define OTG_DIEP volatile struct otg_diep * const
#define OTG_DOEP volatile struct otg_doep * const
#define OTG_PCGCCTL volatile struct otg_pcgcctl * const
#define OTG_DFIFO volatile struct otg_dfifo * const

/* C-accessible registers. */
#if conf_port == PORT_FS
#define OTG_BASE USB_OTG_FS_BASE
#else
#define OTG_BASE USB_OTG_HS_BASE
#endif
static OTG otg = (struct otg *)(OTG_BASE + 0x000);
static OTGH otgh = (struct otgh *)(OTG_BASE + 0x400);
static OTGD otgd = (struct otgd *)(OTG_BASE + 0x800);
static OTG_DIEP otg_diep = (struct otg_diep *)(OTG_BASE + 0x900);
static OTG_DOEP otg_doep = (struct otg_doep *)(OTG_BASE + 0xb00);
static OTG_PCGCCTL otg_pcgcctl = (struct otg_pcgcctl *)(OTG_BASE + 0xe00);
static OTG_DFIFO otg_dfifo = (struct otg_dfifo *)(OTG_BASE + 0x1000);

/*
 * Local variables:
 * mode: C
 * c-file-style: "Linux"
 * c-basic-offset: 4
 * tab-width: 4
 * indent-tabs-mode: nil
 * End:
 */
