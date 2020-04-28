/*
 * hw_dwc_otg.c
 * 
 * USB handling for DWC-OTG USB 2.0 controller.
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

#include "hw_dwc_otg.h"

#define RX_NR 8
#define RX_MASK(x) ((x) & (RX_NR-1))

static struct ep {
    struct {
        uint32_t data[USB_FS_MPS / 4];
        uint32_t count;
    } rx[RX_NR];
    uint16_t rxc, rxp;
    bool_t rx_active, tx_ready;
} eps[conf_nr_ep];

static void core_reset(void)
{
    do { delay_us(1); } while (!(otg->grstctl & OTG_GRSTCTL_AHBIDL));
    otg->grstctl |= OTG_GRSTCTL_CSRST;
    do { delay_us(1); } while (otg->grstctl & OTG_GRSTCTL_CSRST);
}

static void flush_tx_fifo(int num)
{
    otg->grstctl = OTG_GRSTCTL_TXFFLSH | OTG_GRSTCTL_TXFNUM(num);
    do { delay_us(1); } while (otg->grstctl & OTG_GRSTCTL_TXFFLSH);
}

static void flush_rx_fifo(void)
{
    otg->grstctl = OTG_GRSTCTL_RXFFLSH;
    do { delay_us(1); } while (otg->grstctl & OTG_GRSTCTL_RXFFLSH);
}

static void ep0_out_start(void)
{
    otg_doep[0].tsiz = (OTG_DOEPTSZ_STUPCNT |
                        OTG_DOEPTSZ_PKTCNT(1)) |
                        OTG_DOEPTSZ_XFERSIZ(3*8);
}

static bool_t is_high_speed(void)
{
    /* 0 == DSTS_ENUMSPD_HS_PHY_30MHZ_OR_60MHZ */
    return ((otgd->dsts >> 1) & 3) == 0;
}

static void prepare_rx(uint8_t epnr)
{
    OTG_DOEP doep = &otg_doep[epnr];
    uint16_t mps = (epnr == 0) ? 64 : (doep->ctl & 0x7ff);
    uint32_t tsiz = doep->tsiz & 0xe0000000;
    int pktcnt = (epnr == 0) ? 1 : RX_NR;

    tsiz |= OTG_DOEPTSZ_PKTCNT(pktcnt);
    tsiz |= OTG_DOEPTSZ_XFERSIZ(mps * pktcnt);
    doep->tsiz = tsiz;

    doep->ctl |= OTG_DOEPCTL_CNAK | OTG_DOEPCTL_EPENA;

    eps[epnr].rx_active = TRUE;
}

static void read_packet(void *p, int len)
{
    uint32_t *_p = p;
    unsigned int n = (len + 3) / 4;
    while (n--)
        *_p++ = otg_dfifo[0].x[0];
}

static void write_packet(const void *p, uint8_t epnr, int len)
{
    const uint32_t *_p = p;
    unsigned int n = (len + 3) / 4;
    while (n--)
        otg_dfifo[epnr].x[0] = *_p++;
}

static void fifos_init(void)
{
    unsigned int i, base, tx_sz, rx_sz, fifo_sz;

    /* F7 OTG: FS 1.25k FIFO RAM, HS 4k FIFO RAM. */
    fifo_sz = ((conf_port == PORT_FS) ? 0x500 : 0x1000) >> 2;
    rx_sz = fifo_sz / 2;
    tx_sz = fifo_sz / conf_nr_ep;

    otg->grxfsiz = rx_sz;

    base = rx_sz;
    otg->dieptxf0 = (tx_sz << 16) | base;
    for (i = 1; i < conf_nr_ep; i++) {
        base += tx_sz;
        otg->dieptxf[i-1] = (tx_sz << 16) | base;
    }
}

void hw_usb_init(void)
{
    int i;

    /*
     * HAL_PCD_MspInit
     */

    switch (conf_port) {
    case PORT_FS:
        gpio_set_af(gpioa, 11, 10);
        gpio_set_af(gpioa, 12, 10);
        gpio_configure_pin(gpioa, 11, AFO_pushpull(IOSPD_HIGH));
        gpio_configure_pin(gpioa, 12, AFO_pushpull(IOSPD_HIGH));
        rcc->ahb2enr |= RCC_AHB2ENR_OTGFSEN;
        break;
    case PORT_HS:
        gpio_set_af(gpiob, 14, 12);
        gpio_set_af(gpiob, 15, 12);
        gpio_configure_pin(gpiob, 14, AFO_pushpull(IOSPD_HIGH));
        gpio_configure_pin(gpiob, 15, AFO_pushpull(IOSPD_HIGH));
        rcc->ahb1enr |= RCC_AHB1ENR_OTGHSEN;
        break;
    default:
        ASSERT(0);
    }

    peripheral_clock_delay();

    /*
     * USB_CoreInit
     */

    if (conf_iface == IFACE_FS) {
        /* Select Full Speed PHY. */
        otg->gusbcfg |= OTG_GUSBCFG_PHYSEL;
        /* PHY selection must be followed by a core reset. */
        core_reset();
        /* Activate FS transceiver. */
        otg->gccfg |= OTG_GCCFG_PWRDWN;
    } else {
        ASSERT(0);
    }

    /*
     * USB_SetCurrentMode
     */

    /* Mode select followed by required 25ms delay. */
    otg->gusbcfg |= OTG_GUSBCFG_FDMOD;
    delay_ms(25);

    /*
     * USB_DevInit
     */

    for (i = 0; i < ARRAY_SIZE(otg->dieptxf); i++)
        otg->dieptxf[i] = 0;

    /* Override Vbus sense */
    otg->gccfg &= ~OTG_GCCFG_VBDEN;
    otg->gotgctl |= (OTG_GOTGCTL_BVALOVAL | OTG_GOTGCTL_BVALOEN); 

    /* Restart PHY clock. */
    otg_pcgcctl->pcgcctl = 0;

    /* USB_SetDevSpeed */
    if (conf_iface == IFACE_FS) {
        otgd->dcfg = OTG_DCFG_DSPD(3); /* Full Speed */
    } else {
        ASSERT(0);
    }

    flush_tx_fifo(0x10);
    flush_rx_fifo();

    /* Clear endpoints state. */
    otgd->diepmsk = otgd->doepmsk = otgd->daintmsk = 0;
    for (i = 0; i < conf_nr_ep; i++) {
        bool_t ena = !!(otg_diep[i].ctl & OTG_DIEPCTL_EPENA);
        otg_diep[i].ctl =
            (!ena ? 0 : ((i == 0)
                         ? OTG_DIEPCTL_SNAK
                         : OTG_DIEPCTL_SNAK | OTG_DIEPCTL_EPDIS));
        otg_diep[i].tsiz = 0;
        otg_diep[i].intsts = 0xffff;
    }
    for (i = 0; i < conf_nr_ep; i++) {
        bool_t ena = !!(otg_doep[i].ctl & OTG_DOEPCTL_EPENA);
        otg_doep[i].ctl =
            (!ena ? 0 : ((i == 0)
                         ? OTG_DOEPCTL_SNAK
                         : OTG_DOEPCTL_SNAK | OTG_DOEPCTL_EPDIS));
        otg_doep[i].tsiz = 0;
        otg_doep[i].intsts = 0xffff;
    }
    otg->gintsts = ~0;
    otg->gintmsk = (OTG_GINT_USBRST |
                    OTG_GINT_ENUMDNE |
                    OTG_GINT_IEPINT |
                    OTG_GINT_OEPINT |
                    OTG_GINT_RXFLVL);

    fifos_init();

    /* HAL_PCD_Start, USB_DevConnect */
    otgd->dctl &= ~OTG_DCTL_SDIS;
    delay_ms(3);
}

void hw_usb_deinit(void)
{
    switch (conf_port) {
    case PORT_FS:
        gpio_configure_pin(gpioa, 11, GPI_floating);
        gpio_configure_pin(gpioa, 12, GPI_floating);
        rcc->ahb2enr &= ~RCC_AHB2ENR_OTGFSEN;
        break;
    case PORT_HS:
        gpio_configure_pin(gpiob, 14, GPI_floating);
        gpio_configure_pin(gpiob, 15, GPI_floating);
        rcc->ahb1enr &= ~RCC_AHB1ENR_OTGHSEN;
        break;
    default:
        ASSERT(0);
    }
}

int ep_rx_ready(uint8_t epnr)
{
    struct ep *ep = &eps[epnr];
    return (ep->rxc != ep->rxp) ? ep->rx[RX_MASK(ep->rxc)].count : -1;
}

bool_t ep_tx_ready(uint8_t epnr)
{
    return eps[epnr].tx_ready;
}

void usb_read(uint8_t epnr, void *buf, uint32_t len)
{
    struct ep *ep = &eps[epnr];
    memcpy(buf, ep->rx[RX_MASK(ep->rxc++)].data, len);
    if (!ep->rx_active && (ep->rxc == ep->rxp))
        prepare_rx(epnr);
}

void usb_write(uint8_t epnr, const void *buf, uint32_t len)
{
    OTG_DIEP diep = &otg_diep[epnr];

    diep->tsiz = OTG_DIEPTSIZ_PKTCNT(1) | len;

//    if (len != 0)
//        otgd->diepempmsk |= 1u << epnr;

    diep->ctl |= OTG_DIEPCTL_CNAK | OTG_DIEPCTL_EPENA;
    write_packet(buf, epnr, len);
    eps[epnr].tx_ready = FALSE;
}

void usb_stall(uint8_t epnr)
{
    otg_diep[epnr].ctl |= OTG_DIEPCTL_STALL;
    otg_doep[epnr].ctl |= OTG_DOEPCTL_STALL;
}

void usb_configure_ep(uint8_t epnr, uint8_t type, uint32_t size)
{
    bool_t in = !!(epnr & 0x80);
    epnr &= 0x7f;

    if (type == EPT_DBLBUF)
        type = EPT_BULK;

    if (in || (epnr == 0)) {
        otgd->daintmsk |= 1u << epnr;
        if (!(otg_diep[epnr].ctl & OTG_DIEPCTL_USBAEP)) {
            otg_diep[epnr].ctl |= 
                OTG_DIEPCTL_MPSIZ(size) |
                OTG_DIEPCTL_EPTYP(type) |
                OTG_DIEPCTL_TXFNUM(epnr) |
                OTG_DIEPCTL_SD0PID |
                OTG_DIEPCTL_USBAEP;
        }
        eps[epnr].tx_ready = TRUE;
    }

    if (!in) {
        otgd->daintmsk |= 1u << (epnr + 16);
        if (!(otg_doep[epnr].ctl & OTG_DOEPCTL_USBAEP)) {
            otg_doep[epnr].ctl |= 
                OTG_DOEPCTL_MPSIZ(size) |
                OTG_DOEPCTL_EPTYP(type) |
                OTG_DIEPCTL_SD0PID |
                OTG_DOEPCTL_USBAEP;
        }
        eps[epnr].rxc = eps[epnr].rxp = 0;
        prepare_rx(epnr);
    }
}

void usb_setaddr(uint8_t addr)
{
    otgd->dcfg = (otgd->dcfg & ~OTG_DCFG_DAD(0x7f)) | OTG_DCFG_DAD(addr);
}

static void handle_reset(void)
{
    int i;

    /* Initialise core. */
    otgd->dctl &= ~OTG_DCTL_RWUSIG;
    flush_tx_fifo(0x10);
    for (i = 0; i < conf_nr_ep; i++) {
        otg_diep[i].ctl &= ~(OTG_DIEPCTL_STALL |
                             OTG_DIEPCTL_USBAEP |
                             OTG_DIEPCTL_MPSIZ(0x7ff) |
                             OTG_DIEPCTL_TXFNUM(0xf) |
                             OTG_DIEPCTL_SD0PID |
                             OTG_DIEPCTL_EPTYP(3));
        otg_doep[i].ctl &= ~(OTG_DOEPCTL_STALL |
                             OTG_DOEPCTL_USBAEP |
                             OTG_DOEPCTL_MPSIZ(0x7ff) |
                             OTG_DOEPCTL_SD0PID |
                             OTG_DOEPCTL_EPTYP(3));
    }
    otgd->daintmsk = 0x10001u;
    otgd->doepmsk |= (OTG_DOEPMSK_STUPM |
                      OTG_DOEPMSK_XFRCM |
                      OTG_DOEPMSK_EPDM |
                      OTG_DOEPMSK_STSPHSRXM |
                      OTG_DOEPMSK_NAKM);
    otgd->diepmsk |= (OTG_DIEPMSK_TOM |
                      OTG_DIEPMSK_XFRCM |
                      OTG_DIEPMSK_EPDM);

    /* Set address 0. */
    otgd->dcfg &= ~OTG_DCFG_DAD(0x7f);
    ep0_out_start();

    /* Reinitialise class-specific subsystem. */
    usb_cdc_acm_ops.reset();

    /* Clear endpoint soft state. */
    memset(eps, 0, sizeof(eps));

    /* Clear any in-progress Control Transfer. */
    ep0.data_len = -1;
    ep0.tx.todo = -1;
}

static void handle_rx_transfer(void)
{
    uint32_t grxsts = otg->grxstsp;
    unsigned int bcnt = OTG_RXSTS_BCNT(grxsts);
    unsigned int epnr = OTG_RXSTS_CHNUM(grxsts);
    unsigned int rxp;
    struct ep *ep = &eps[epnr];

    switch (OTG_RXSTS_PKTSTS(grxsts)) {
    case STS_SETUP_UPDT:
        bcnt = 8;
    case STS_DATA_UPDT:
        ASSERT(ep->rx_active);
        ASSERT((uint16_t)(ep->rxp - ep->rxc) < RX_NR);
        rxp = RX_MASK(ep->rxp++);
        read_packet(ep->rx[rxp].data, bcnt);
        ep->rx[rxp].count = bcnt;
        break;
    default:
        break;
    }
}

static void handle_oepint(uint8_t epnr)
{
    uint32_t oepint = otg_doep[epnr].intsts & otgd->doepmsk;
    struct ep *ep = &eps[epnr];

    otg_doep[epnr].intsts = oepint;

    if (oepint & OTG_DOEPMSK_XFRCM) {
        ASSERT(ep->rx_active);
        ep->rx_active = FALSE;
        if (epnr == 0)
            handle_rx_ep0(FALSE);
    }

    if (oepint & OTG_DOEPMSK_STUPM) {
        ASSERT(ep->rx_active);
        ep->rx_active = FALSE;
        if (epnr == 0)
            handle_rx_ep0(TRUE);
    }

    if (!ep->rx_active && (ep->rxc == ep->rxp))
        prepare_rx(epnr);
}

static void handle_iepint(uint8_t epnr)
{
    uint32_t iepint = otg_diep[epnr].intsts, iepmsk;

    iepmsk = otgd->diepmsk | (((otgd->diepempmsk >> epnr) & 1) << 7);
    iepint = otg_diep[epnr].intsts & iepmsk;

    otg_diep[epnr].intsts = iepint;

    if (iepint & OTG_DIEPINT_XFRC) {
        otgd->diepempmsk &= ~(1 << epnr);
        eps[epnr].tx_ready = TRUE;
        if (epnr == 0)
            handle_tx_ep0();
    }

    if (iepint & OTG_DIEPINT_TXFE) {
        ASSERT(0);
    }
}

void usb_process(void)
{
    uint32_t gintsts = otg->gintsts & otg->gintmsk;

    if (gintsts & OTG_GINT_OEPINT) {
        uint16_t mask = (otgd->daint & otgd->daintmsk) >> 16;
        int epnr;
        for (epnr = 0; mask != 0; mask >>= 1, epnr++) {
            if (mask & 1)
                handle_oepint(epnr);
        }
    }

    if (gintsts & OTG_GINT_IEPINT) {
        uint16_t mask = otgd->daint & otgd->daintmsk;
        int epnr;
        for (epnr = 0; mask != 0; mask >>= 1, epnr++) {
            if (mask & 1)
                handle_iepint(epnr);
        }
    }

    if (gintsts & OTG_GINT_ENUMDNE) {
        bool_t hs;
        printk("[ENUMDNE]\n");
        /* USB_ActivateSetup */
        otg_diep[0].ctl &= ~OTG_DIEPCTL_MPSIZ(0x7ff);
        otgd->dctl |= OTG_DCTL_CGINAK;
        /* USB_SetTurnaroundTime */
        hs = is_high_speed();
        /* Ref. Table 232, FS Mode */
        otg->gusbcfg |= OTG_GUSBCFG_TRDT(hs ? 9 : 6);
        usb_configure_ep(0, EPT_CONTROL, USB_FS_MPS);
        otg->gintsts = OTG_GINT_ENUMDNE;
    }

    if (gintsts & OTG_GINT_USBRST) {
        printk("[USBRST]\n");
        handle_reset();
        otg->gintsts = OTG_GINT_USBRST;
    }

    if (gintsts & OTG_GINT_RXFLVL) {
        handle_rx_transfer();
    }
}

/*
 * Local variables:
 * mode: C
 * c-file-style: "Linux"
 * c-basic-offset: 4
 * tab-width: 4
 * indent-tabs-mode: nil
 * End:
 */
