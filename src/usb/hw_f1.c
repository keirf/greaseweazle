/*
 * hw_f1.c
 * 
 * USB handling for STM32F10x devices (except 105/107).
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

static uint16_t buf_end;

static struct {
    /* We track which endpoints have been marked CTR (Correct TRansfer). On 
     * receive side, checking EPR_STAT_RX == NAK races update of the Buffer 
     * Descriptor's COUNT_RX by the hardware. */
    bool_t rx_ready;
    bool_t tx_ready;
} eps[8];

void usb_init(void)
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

    /* Indicate we are connected by pulling up D+. */
    gpio_configure_pin(gpioa, 0, GPO_pushpull(_2MHz, HIGH));
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

int ep_rx_ready(uint8_t ep)
{
    uint16_t count, epr;
    volatile struct usb_bufd *bd;

    if (!eps[ep].rx_ready)
        return -1;

    bd = &usb_bufd[ep];
    epr = usb->epr[ep];

    count = !(epr & USB_EPR_EP_KIND_DBL_BUF) ? bd->count_rx
        : (epr & 0x0040) ? bd->count_1 : bd->count_0;

    return count & 0x3ff;
}

bool_t ep_tx_ready(uint8_t ep)
{
    return eps[ep].tx_ready;
}

void usb_read(uint8_t ep, void *buf, uint32_t len)
{
    unsigned int i, base;
    uint16_t epr = usb->epr[ep], *p = buf;
    volatile struct usb_bufd *bd = &usb_bufd[ep];

    if (epr & USB_EPR_EP_KIND_DBL_BUF) {
        base = (epr & 0x0040) ? bd->addr_1 : bd->addr_0;
        /* If HW is pointing at same buffer as us, we have to process both 
         * buffers, and should defer clearing rx_ready until we've done so. */
        if ((epr ^ (epr>>8)) & 0x40)
            eps[ep].rx_ready = FALSE;
    } else {
        base = bd->addr_rx;
        eps[ep].rx_ready = FALSE;
    }
    base = (uint16_t)base >> 1;

    for (i = 0; i < len/2; i++)
        *p++ = usb_buf[base + i];
    if (len&1)
        *(uint8_t *)p = usb_buf[base + i];

    if (epr & USB_EPR_EP_KIND_DBL_BUF) {
        /* Toggle SW_BUF. Status remains VALID at all times. */
        epr &= 0x070f; /* preserve rw & t fields */
        epr |= 0x80c0; /* preserve rc_w0 fields, toggle SW_BUF */
    } else {
        /* Set status NAK->VALID. */
        epr &= 0x370f; /* preserve rw & t fields (except STAT_RX) */
        epr |= 0x8080; /* preserve rc_w0 fields */
        epr ^= USB_EPR_STAT_RX(USB_STAT_VALID); /* modify STAT_RX */
    }
    usb->epr[ep] = epr;
}

void usb_write(uint8_t ep, const void *buf, uint32_t len)
{
    unsigned int i, base;
    uint16_t epr = usb->epr[ep];
    const uint16_t *p = buf;
    volatile struct usb_bufd *bd = &usb_bufd[ep];

    if (epr & USB_EPR_EP_KIND_DBL_BUF) {
        if (epr & 0x4000) {
            base = bd->addr_1;
            bd->count_1 = len;
        } else {
            base = bd->addr_0;
            bd->count_0 = len;
        }
        /* If HW is pointing at same buffer as us, we have space for two
         * packets, and do not need to clear tx_ready. */
        if ((epr ^ (epr>>8)) & 0x40)
            eps[ep].tx_ready = FALSE;
    } else {
        base = bd->addr_tx;
        bd->count_tx = len;
        eps[ep].tx_ready = FALSE;
    }
    base = (uint16_t)base >> 1;

    for (i = 0; i < len/2; i++)
        usb_buf[base + i] = *p++;
    if (len&1)
        usb_buf[base + i] = *(const uint8_t *)p;

    if (epr & USB_EPR_EP_KIND_DBL_BUF) {
        /* Toggle SW_BUF. Status remains VALID at all times. */
        epr &= 0x070f; /* preserve rw & t fields */
        epr |= 0xc080; /* preserve rc_w0 fields, toggle SW_BUF */
    } else {
        /* Set status NAK->VALID. */
        epr &= 0x073f; /* preserve rw & t fields (except STAT_TX) */
        epr |= 0x8080; /* preserve rc_w0 fields */
        epr ^= USB_EPR_STAT_TX(USB_STAT_VALID); /* modify STAT_TX */
    }
    usb->epr[ep] = epr;
}

static void usb_write_ep0(void)
{
    uint32_t len;

    if ((ep0.tx.todo < 0) || !ep_tx_ready(0))
        return;

    len = min_t(uint32_t, ep0.tx.todo, USB_FS_MPS);
    usb_write(0, ep0.tx.p, len);

    ep0.tx.p += len;
    ep0.tx.todo -= len;

    if (ep0.tx.todo == 0) {
        /* USB Spec 1.1, Section 5.5.3: Data stage of a control transfer is
         * complete when we have transferred the exact amount of data specified
         * during Setup *or* transferred a short/zero packet. */
        if (!ep0.tx.trunc || (len < USB_FS_MPS))
            ep0.tx.todo = -1;
    }
}

static void usb_stall(uint8_t ep)
{
    uint16_t epr = usb->epr[ep];
    epr &= 0x073f;
    epr |= 0x8080;
    epr ^= USB_EPR_STAT_TX(USB_STAT_STALL);
    usb->epr[ep] = epr;
}

void usb_configure_ep(uint8_t ep, uint8_t type, uint32_t size)
{
    uint16_t old_epr, new_epr;
    bool_t in, dbl_buf;
    volatile struct usb_bufd *bd;

    in = !!(ep & 0x80);
    ep &= 0x7f;
    bd = &usb_bufd[ep];

    old_epr = usb->epr[ep];
    new_epr = 0;

    dbl_buf = (type == USB_EP_TYPE_BULK_DBLBUF);
    if (dbl_buf) {
        ASSERT(ep != 0);
        type = USB_EP_TYPE_BULK;
        new_epr |= USB_EPR_EP_KIND_DBL_BUF;
        bd->addr_0 = buf_end;
        bd->addr_1 = buf_end + size;
        buf_end += 2*size;
    }

    /* Sets: Type and Endpoint Address.
     * Clears: CTR_RX and CTR_TX. */
    new_epr |= USB_EPR_EP_TYPE(type) | USB_EPR_EA(ep);

    if (in || (ep == 0)) {
        if (dbl_buf) {
            bd->count_0 = bd->count_1 = 0;
            /* TX: Sets SW_BUF. */
            new_epr |= (old_epr & 0x4000) ^ 0x4000;
            /* TX: Clears data toggle and sets status to VALID. */
            new_epr |= (old_epr & 0x0070) ^ USB_EPR_STAT_TX(USB_STAT_VALID);
        } else {
            bd->addr_tx = buf_end;
            buf_end += size;
            bd->count_tx = 0;
            /* TX: Clears data toggle and sets status to NAK. */
            new_epr |= (old_epr & 0x0070) ^ USB_EPR_STAT_TX(USB_STAT_NAK);
        }
        /* IN Endpoint is immediately ready to transmit. */
        eps[ep].tx_ready = TRUE;
    }

    if (!in) {
        if (dbl_buf) {
            bd->count_0 = bd->count_1 = 0x8400; /* USB_FS_MPS = 64 bytes */
            /* RX: Clears SW_BUF. */
            new_epr |= old_epr & 0x0040;
        } else {
            bd->addr_rx = buf_end;
            buf_end += size;
            bd->count_rx = 0x8400; /* USB_FS_MPS = 64 bytes */
        }
        /* RX: Clears data toggle and sets status to VALID. */
        new_epr |= (old_epr & 0x7000) ^ USB_EPR_STAT_RX(USB_STAT_VALID);
        /* OUT Endpoint must wait for a packet from the Host. */
        eps[ep].rx_ready = FALSE;
    }

    usb->epr[ep] = new_epr;
}

static void handle_reset(void)
{
    /* Reinitialise floppy subsystem. */
    floppy_reset();

    /* Clear endpoint soft state. */
    memset(eps, 0, sizeof(eps));

    /* Clear any in-progress Control Transfer. */
    ep0.data_len = -1;
    ep0.tx.todo = -1;

    /* Prepare for Enumeration: Set up Endpoint 0 at Address 0. */
    pending_addr = 0;
    buf_end = 64;
    usb_configure_ep(0, USB_EP_TYPE_CONTROL, USB_FS_MPS);
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

static void handle_rx_transfer(uint8_t ep)
{
    uint16_t epr = usb->epr[ep];
    bool_t ready;

    clear_ctr(ep, USB_EPR_CTR_RX);
    eps[ep].rx_ready = TRUE;

    /* We only handle Control Transfers here (endpoint 0). */
    if (ep != 0)
        return;

    ready = FALSE;

    if (epr & USB_EPR_SETUP) {

        /* Control Transfer: Setup Stage. */
        ep0.data_len = 0;
        ep0.tx.todo = -1;
        usb_read(ep, &ep0.req, sizeof(ep0.req));
        ready = ep0_data_in() || (ep0.req.wLength == 0);

    } else if (ep0.data_len < 0) {

        /* Unexpected Transaction */
        usb_stall(0);
        usb_read(ep, NULL, 0);

    } else if (ep0_data_out()) {

        /* OUT Control Transfer: Data from Host. */
        uint32_t len = usb_bufd[ep].count_rx & 0x3ff;
        int l = 0;
        if (ep0.data_len < sizeof(ep0.data))
            l = min_t(int, sizeof(ep0.data)-ep0.data_len, len);
        usb_read(ep, &ep0.data[ep0.data_len], l);
        ep0.data_len += len;
        if (ep0.data_len >= ep0.req.wLength) {
            ep0.data_len = ep0.req.wLength; /* clip */
            ready = TRUE;
        }

    } else {

        /* IN Control Transfer: Status from Host. */
        usb_read(ep, NULL, 0);
        ep0.tx.todo = -1;
        ep0.data_len = -1; /* Complete */

    }

    /* Are we ready to handle the Control Request? */
    if (!ready)
        return;

    /* Attempt to handle the Control Request: */
    if (!handle_control_request()) {

        /* Unhandled Control Transfer: STALL */
        usb_stall(0);
        ep0.data_len = -1; /* Complete */

    } else if (ep0_data_in()) {

        /* IN Control Transfer: Send Data to Host. */
        ep0.tx.p = ep0.data;
        ep0.tx.todo = ep0.data_len;
        ep0.tx.trunc = (ep0.data_len < ep0.req.wLength);
        usb_write_ep0();

    } else {

        /* OUT Control Transfer: Send Status to Host. */
        ep0.tx.p = NULL;
        ep0.tx.todo = 0;
        ep0.tx.trunc = FALSE;
        usb_write_ep0();
        ep0.data_len = -1; /* Complete */

    }
}

static void handle_tx_transfer(uint8_t ep)
{
    clear_ctr(ep, USB_EPR_CTR_TX);
    eps[ep].tx_ready = TRUE;

    /* We only handle Control Transfers here (endpoint 0). */
    if (ep != 0)
        return;

    usb_write_ep0();

    if (pending_addr && (ep0.tx.todo == -1)) {
        /* We have just completed the Status stage of a SET_ADDRESS request. 
         * Now is the time to apply the address update. */
        usb->daddr = USB_DADDR_EF | USB_DADDR_ADD(pending_addr);
        pending_addr = 0;
    }
}

void usb_process(void)
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

    /* We ignore all the below... */

    if (istr & USB_ISTR_SUSP) {
//        printk("[SUSP]\n");
    }

    if (istr & USB_ISTR_SOF) {
//        printk("[SOF]\n");
    }

    if (istr & USB_ISTR_ESOF) {
//        printk("[ESOF]\n");
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
