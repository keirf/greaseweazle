/*
 * hw_usbd_at32f4.c
 * 
 * USB handling for AT32F4xx USBD peripheral. This is separate from the STM32
 * equivalent as Artery messed up implementation of double-buffered endpoints.
 * Thus to achieve line rate requires IRQ trickery to quickly post new buffers.
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

#include "hw_usbd.h"

void IRQ_19(void) __attribute__((alias("IRQ_USB_HP")));
#define USB_HP_IRQ 19

static uint16_t buf_end;
static uint8_t pending_addr;

/* Double-buffer endpoints: RX/TX buffer rings interfacing to USB IRQ. */
#define NBUF 2
static struct buf {
    uint16_t data[USB_FS_MPS / 2];
    uint32_t count;
} rx_buf[NBUF], tx_buf[NBUF];

#define BUF_MASK(_ep, _idx) (((_ep)->_idx) & (NBUF-1))

static struct ep {
    bool_t is_dblbuf;
    union {
        struct {
            /* Normal (non-double-buffered) endpoints: We track which 
             * endpoints have been marked CTR (Correct TRansfer). On receive 
             * side, checking EPR_STAT_RX == NAK races update of the Buffer
             * Descriptor's COUNT_RX by the hardware. */
            bool_t rx_ready;
            bool_t tx_ready;
        } std;
        struct {
            /* is_dblbuf: Non-IRQ context needs to kick the pipeline. */
            bool_t kick;
            /* is_dblbuf: {rx,tx}_buf[] ring indexes */
            uint16_t bufc, bufp;
            /* is_dblbuf: number of hw slots filled */
            unsigned int tx_hw_slots;
        } db;
    };
} eps[8];

static void handle_dblbuf_tx_transfer(uint8_t epnr);
static void handle_dblbuf_rx_transfer(uint8_t epnr);

static bool_t usbd_has_highspeed(void)
{
    return FALSE;
}

static bool_t usbd_is_highspeed(void)
{
    return FALSE;
}

static void usbd_init(void)
{
    /* Turn on clock. */
    rcc->apb1enr |= RCC_APB1ENR_USBEN;

    /* Exit power-down state. */
    usb->cntr &= ~USB_CNTR_PDWN;
    delay_us(10);

    /* Exit reset state. */
    usb->cntr &= ~USB_CNTR_FRES;
    delay_us(10);

    /* Clear IRQ state. */
    usb->istr = 0;

    IRQx_set_prio(USB_HP_IRQ, USB_IRQ_PRI);
    IRQx_enable(USB_HP_IRQ);
}

static void usbd_deinit(void)
{
    rcc->apb1enr &= ~RCC_APB1ENR_USBEN;
}

#if 0
static void dump_ep(uint8_t ep)
{
    const static char *names[] = { "DISA", "STAL", "NAK ", "VALI" };
    uint16_t epr;
    ep &= 0x7f;
    epr = usb->epr[ep];
    printk("[EP%u: Rx:%c%c(%s)%04x:%02u Tx:%c%c(%s)%04x:%02u %c]",
           ep,
           (epr & USB_EPR_CTR_RX) ? 'C' : ' ',
           (epr & USB_EPR_DTOG_RX) ? 'D' : ' ',
           names[(epr>>12)&3],
           usb_bufd[ep].addr_rx, usb_bufd[ep].count_rx & 0x3ff,
           (epr & USB_EPR_CTR_TX) ? 'C' : ' ',
           (epr & USB_EPR_DTOG_TX) ? 'D' : ' ',
           names[(epr>>4)&3],
           usb_bufd[ep].addr_tx, usb_bufd[ep].count_tx & 0x3ff,
           (epr & USB_EPR_SETUP) ? 'S' : ' ');
}
#endif

static int usbd_ep_rx_ready(uint8_t epnr)
{
    volatile struct usb_bufd *bd;
    struct ep *ep = &eps[epnr];

    if (ep->is_dblbuf)
        return ((ep->db.bufc != ep->db.bufp)
                ? rx_buf[BUF_MASK(ep, db.bufc)].count
                : -1);

    if (!ep->std.rx_ready)
        return -1;

    bd = &usb_bufd[epnr];
    return bd->count_rx & 0x3ff;
}

static bool_t usbd_ep_tx_ready(uint8_t epnr)
{
    struct ep *ep = &eps[epnr];
    if (ep->is_dblbuf)
        return (uint16_t)(ep->db.bufp - ep->db.bufc) < NBUF;
    return ep->std.tx_ready;
}

static void usbd_read(uint8_t epnr, void *buf, uint32_t len)
{
    unsigned int i, base;
    uint16_t epr = usb->epr[epnr], *p = buf;
    volatile struct usb_bufd *bd = &usb_bufd[epnr];
    struct ep *ep = &eps[epnr];

    if (ep->is_dblbuf) {
        memcpy(buf, rx_buf[BUF_MASK(ep, db.bufc)].data, len);
        barrier(); /* read data /then/ update consumer */
        ep->db.bufc++;
        if (ep->db.kick) {
            uint32_t oldpri = IRQ_save(USB_IRQ_PRI);
            if (ep->db.kick)
                handle_dblbuf_rx_transfer(epnr);
            IRQ_restore(oldpri);
        }
        return;
    }

    base = bd->addr_rx;
    ep->std.rx_ready = FALSE;
    base = (uint16_t)base >> 1;

    for (i = 0; i < len/2; i++)
        *p++ = usb_buf[base + i];
    if (len&1)
        *(uint8_t *)p = usb_buf[base + i];

    /* Set status NAK->VALID. */
    epr &= 0x370f; /* preserve rw & t fields (except STAT_RX) */
    epr |= 0x8080; /* preserve rc_w0 fields */
    epr ^= USB_EPR_STAT_RX(USB_STAT_VALID); /* modify STAT_RX */
    usb->epr[epnr] = epr;
}

static void usbd_write(uint8_t epnr, const void *buf, uint32_t len)
{
    unsigned int i, base;
    uint16_t epr = usb->epr[epnr];
    const uint16_t *p = buf;
    volatile struct usb_bufd *bd = &usb_bufd[epnr];
    struct ep *ep = &eps[epnr];

    if (ep->is_dblbuf) {
        struct buf *b = &tx_buf[BUF_MASK(ep, db.bufp)];
        memcpy(b->data, buf, len);
        b->count = len;
        barrier(); /* write data /then/ update producer */
        ep->db.bufp++;
        if (ep->db.kick) {
            uint32_t oldpri = IRQ_save(USB_IRQ_PRI);
            if (ep->db.kick)
                handle_dblbuf_tx_transfer(epnr);
            IRQ_restore(oldpri);
        }
        return;
    }

    base = bd->addr_tx;
    bd->count_tx = len;
    ep->std.tx_ready = FALSE;
    base = (uint16_t)base >> 1;

    for (i = 0; i < len/2; i++)
        usb_buf[base + i] = *p++;
    if (len&1)
        usb_buf[base + i] = *(const uint8_t *)p;

    /* Set status NAK->VALID. */
    epr &= 0x073f; /* preserve rw & t fields (except STAT_TX) */
    epr |= 0x8080; /* preserve rc_w0 fields */
    epr ^= USB_EPR_STAT_TX(USB_STAT_VALID); /* modify STAT_TX */
    usb->epr[epnr] = epr;
}

static void usbd_stall(uint8_t ep)
{
    uint16_t epr = usb->epr[ep];
    epr &= 0x073f;
    epr |= 0x8080;
    epr ^= USB_EPR_STAT_TX(USB_STAT_STALL);
    usb->epr[ep] = epr;
}

static void usbd_configure_ep(uint8_t epnr, uint8_t type, uint32_t size)
{
    static const uint8_t types[] = {
        [EPT_CONTROL] = USB_EP_TYPE_CONTROL,
        [EPT_ISO] = USB_EP_TYPE_ISO,
        [EPT_BULK] = USB_EP_TYPE_BULK,
        [EPT_INTERRUPT] = USB_EP_TYPE_INTERRUPT
    };

    uint16_t old_epr, new_epr;
    bool_t in, dbl_buf;
    volatile struct usb_bufd *bd;
    struct ep *ep;

    in = !!(epnr & 0x80);
    epnr &= 0x7f;
    ep = &eps[epnr];
    bd = &usb_bufd[epnr];

    old_epr = usb->epr[epnr];
    new_epr = 0;

    dbl_buf = (type == EPT_DBLBUF);
    if (dbl_buf) {
        ASSERT(epnr != 0);
        type = EPT_BULK;
        new_epr |= USB_EPR_EP_KIND_DBL_BUF;
        bd->addr_0 = buf_end;
        bd->addr_1 = buf_end + size;
        buf_end += 2*size;
        ep->is_dblbuf = TRUE;
        ep->db.bufc = ep->db.bufp = ep->db.tx_hw_slots = 0;
    }

    type = types[type];

    /* Sets: Type and Endpoint Address.
     * Clears: CTR_RX and CTR_TX. */
    new_epr |= USB_EPR_EP_TYPE(type) | USB_EPR_EA(epnr);

    if (in || (epnr == 0)) {
        if (dbl_buf) {
            bd->count_0 = bd->count_1 = 0;
            /* TX: Clears SW_BUF. */
            new_epr |= old_epr & 0x4000;
            /* TX: Clears data toggle and sets status to VALID. */
            new_epr |= (old_epr & 0x0070) ^ USB_EPR_STAT_TX(USB_STAT_VALID);
            ep->db.kick = TRUE;
        } else {
            bd->addr_tx = buf_end;
            buf_end += size;
            bd->count_tx = 0;
            /* TX: Clears data toggle and sets status to NAK. */
            new_epr |= (old_epr & 0x0070) ^ USB_EPR_STAT_TX(USB_STAT_NAK);
            /* IN Endpoint is immediately ready to transmit. */
            ep->std.tx_ready = TRUE;
        }
    }

    if (!in) {
        if (dbl_buf) {
            bd->count_0 = bd->count_1 = 0x8400; /* USB_FS_MPS = 64 bytes */
            /* RX: Sets SW_BUF. */
            new_epr |= (old_epr & 0x0040) ^ 0x0040;
            ep->db.kick = FALSE;
        } else {
            bd->addr_rx = buf_end;
            buf_end += size;
            bd->count_rx = 0x8400; /* USB_FS_MPS = 64 bytes */
            /* OUT Endpoint must wait for a packet from the Host. */
            ep->std.rx_ready = FALSE;
        }
        /* RX: Clears data toggle and sets status to VALID. */
        new_epr |= (old_epr & 0x7000) ^ USB_EPR_STAT_RX(USB_STAT_VALID);
    }

    barrier(); /* initialise soft flags /then/ enable endpoint */
    usb->epr[epnr] = new_epr;
}

static void usbd_setaddr(uint8_t addr)
{
    pending_addr = addr;
}

static void handle_reset(void)
{
    /* Reinitialise class-specific subsystem. */
    usb_cdc_acm_ops.reset();

    /* Clear endpoint soft state. */
    memset(eps, 0, sizeof(eps));

    /* Clear any in-progress Control Transfer. */
    ep0.data_len = -1;
    ep0.tx.todo = -1;

    /* Prepare for Enumeration: Set up Endpoint 0 at Address 0. */
    pending_addr = 0;
    buf_end = 64;
    usb_configure_ep(0, EPT_CONTROL, EP0_MPS);
    usb->daddr = USB_DADDR_EF | USB_DADDR_ADD(0);
    usb->istr &= ~USB_ISTR_RESET;
}

static void clear_ctr(uint8_t ep, uint16_t ctr)
{
    uint16_t epr = usb->epr[ep];
    epr &= 0x070f; /* preserve rw & t fields */
    epr |= 0x8080; /* preserve rc_w0 fields */
    epr &= ~ctr;   /* clear specified rc_w0 field */
    usb->epr[ep] = epr;
}

static void handle_rx_transfer(uint8_t epnr)
{
    uint16_t epr = usb->epr[epnr];
    struct ep *ep = &eps[epnr];

    if (ep->is_dblbuf)
        return;

    clear_ctr(epnr, USB_EPR_CTR_RX);
    ep->std.rx_ready = TRUE;

    /* We only handle Control Transfers here (endpoint 0). */
    if (epnr == 0)
        handle_rx_ep0(!!(epr & USB_EPR_SETUP));
}

static void handle_tx_transfer(uint8_t epnr)
{
    struct ep *ep = &eps[epnr];

    if (ep->is_dblbuf)
        return;

    clear_ctr(epnr, USB_EPR_CTR_TX);
    ep->std.tx_ready = TRUE;

    /* We only handle Control Transfers here (endpoint 0). */
    if (epnr != 0)
        return;

    handle_tx_ep0();

    if (pending_addr && (ep0.tx.todo == -1)) {
        /* We have just completed the Status stage of a SET_ADDRESS request. 
         * Now is the time to apply the address update. */
        usb->daddr = USB_DADDR_EF | USB_DADDR_ADD(pending_addr);
        pending_addr = 0;
    }
}

static void usbd_process(void)
{
    uint16_t istr = usb->istr;
    usb->istr = ~istr & 0x7f00;

    if (istr & USB_ISTR_CTR) {
        uint8_t ep = USB_ISTR_GET_EP_ID(istr);
        //dump_ep(ep);
        if (istr & USB_ISTR_DIR)
            handle_rx_transfer(ep);
        else
            handle_tx_transfer(ep);
        //printk(" -> "); dump_ep(ep); printk("\n");
    }

    if (istr & USB_ISTR_PMAOVR) {
        printk("[PMAOVR]\n");
    }

    if (istr & USB_ISTR_ERR) {
        printk("[ERR]\n");
    }

    if (istr & USB_ISTR_WKUP) {
        printk("[WKUP]\n");
    }

    if (istr & USB_ISTR_RESET) {
        printk("[RESET]\n");
        handle_reset();
    }
}

static void handle_dblbuf_rx_transfer(uint8_t epnr)
{
    struct ep *ep;
    volatile struct usb_bufd *bd;
    uint16_t epr, _epr, *p;
    unsigned int i, base, len;
    struct buf *buf;

    ep = &eps[epnr];
    epr = usb->epr[epnr];
    bd = &usb_bufd[epnr];

    if ((uint16_t)(ep->db.bufp - ep->db.bufc) == NBUF) {
        clear_ctr(epnr, USB_EPR_CTR_RX);
        ep->db.kick = TRUE;
        return;
    }

    ep->db.kick = FALSE;

    /* Clear CTR_RX. Toggle SW_BUF. Status remains VALID at all times. */
    _epr = epr;
    _epr &= 0x070f; /* preserve rw & t fields */
    _epr |= 0x80c0; /* preserve rc_w0 fields, toggle SW_BUF */
    _epr &= ~USB_EPR_CTR_RX;
    usb->epr[epnr] = _epr;

    base = (epr & 0x0040) ? bd->addr_0 : bd->addr_1;
    base = (uint16_t)base >> 1;
    len = (epr & 0x0040) ? bd->count_0 : bd->count_1;
    len &= 0x3ff;

    buf = &rx_buf[BUF_MASK(ep, db.bufp++)];
    p = buf->data;
    buf->count = len;

    for (i = 0; i < 64/2; i++)
        *p++ = usb_buf[base + i];
}

static void stuff_dblbuf_tx_packet(uint8_t epnr)
{
    struct ep *ep;
    volatile struct usb_bufd *bd;
    uint16_t epr, *p;
    unsigned int i, base, len;
    struct buf *buf;

    ep = &eps[epnr];
    epr = usb->epr[epnr];
    bd = &usb_bufd[epnr];

    buf = &tx_buf[BUF_MASK(ep, db.bufc++)];
    p = buf->data;
    len = buf->count;

    if (epr & 0x4000) {
        base = bd->addr_1;
        bd->count_1 = len;
    } else {
        base = bd->addr_0;
        bd->count_0 = len;
    }
    base = (uint16_t)base >> 1;

    for (i = 0; i < 64/2; i++)
        usb_buf[base + i] = *p++;

    ep->db.tx_hw_slots++;
}

static void handle_dblbuf_tx_transfer(uint8_t epnr)
{
    struct ep *ep = &eps[epnr];
    uint16_t epr;

    ep->db.kick = (ep->db.bufc == ep->db.bufp) && (ep->db.tx_hw_slots == 0);
    if (ep->db.kick)
        return;

    if (ep->db.tx_hw_slots == 0)
        stuff_dblbuf_tx_packet(epnr);

    /* Toggle SW_BUF. Status remains VALID at all times. */
    epr = usb->epr[epnr];
    epr &= 0x070f; /* preserve rw & t fields */
    epr |= 0xc080; /* preserve rc_w0 fields, toggle SW_BUF */
    usb->epr[epnr] = epr;

    if ((ep->db.tx_hw_slots == 1) && (ep->db.bufc != ep->db.bufp))
        stuff_dblbuf_tx_packet(epnr);
}

static void IRQ_USB_HP(void)
{
    uint16_t istr = usb->istr;
    if (usb->istr & USB_ISTR_CTR) {
        uint8_t epnr = USB_ISTR_GET_EP_ID(istr);
        if (istr & USB_ISTR_DIR) {
            handle_dblbuf_rx_transfer(epnr);
        } else {
            struct ep *ep = &eps[epnr];
            ep->db.tx_hw_slots--;
            clear_ctr(epnr, USB_EPR_CTR_TX);
            handle_dblbuf_tx_transfer(epnr);
        }
    }
}

const struct usb_driver usbd = {
    .init = usbd_init,
    .deinit = usbd_deinit,
    .process = usbd_process,

    .has_highspeed = usbd_has_highspeed,
    .is_highspeed = usbd_is_highspeed,

    .setaddr = usbd_setaddr,

    .configure_ep = usbd_configure_ep,
    .ep_rx_ready = usbd_ep_rx_ready,
    .ep_tx_ready = usbd_ep_tx_ready,
    .read = usbd_read,
    .write = usbd_write,
    .stall = usbd_stall
};

/*
 * Local variables:
 * mode: C
 * c-file-style: "Linux"
 * c-basic-offset: 4
 * tab-width: 4
 * indent-tabs-mode: nil
 * End:
 */
