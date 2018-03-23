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

/* We track which endpoints have been marked CTR (Correct TRansfer).
 * On receive side, checking EPR_STAT_RX == NAK races update of the
 * Buffer Descriptor's COUNT_RX by the hardware. */
static bool_t _ep_rx_ready[8];
static bool_t _ep_tx_ready[8];

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
    return _ep_rx_ready[ep] ? usb_bufd[ep].count_rx & 0x3ff : -1;
}

bool_t ep_tx_ready(uint8_t ep)
{
    return _ep_tx_ready[ep];
}

void usb_read(uint8_t ep, void *buf, uint32_t len)
{
    unsigned int i, base = (uint16_t)usb_bufd[ep].addr_rx >> 1;
    uint16_t epr, *p = buf;

    for (i = 0; i < len/2; i++)
        *p++ = usb_buf[base + i];
    if (len&1)
        *(uint8_t *)p = usb_buf[base + i];

    /* Clear CTR_RX and set status NAK->VALID. */
    epr = usb->epr[ep];
    epr &= 0x370f;
    epr |= 0x0080;
    epr ^= USB_EPR_STAT_RX(USB_STAT_VALID);
    usb->epr[ep] = epr;

    /* Await next CTR_RX notification. */
    _ep_rx_ready[ep] = FALSE;
}

void usb_write(uint8_t ep, const void *buf, uint32_t len)
{
    unsigned int i, base = (uint16_t)usb_bufd[ep].addr_tx >> 1;
    uint16_t epr;
    const uint16_t *p = buf;

    for (i = 0; i < len/2; i++)
        usb_buf[base + i] = *p++;
    if (len&1)
        usb_buf[base + i] = *(const uint8_t *)p;

    usb_bufd[ep].count_tx = len;

    /* Set status NAK->VALID. */
    epr = usb->epr[ep];
    epr &= 0x073f;
    epr |= 0x8080;
    epr ^= USB_EPR_STAT_TX(USB_STAT_VALID);
    usb->epr[ep] = epr;

    /* Await next CTR_TX notification. */
    _ep_tx_ready[ep] = FALSE;
}

static void usb_continue_write_ep0(void)
{
    uint32_t len;

    if ((ep0.tx.todo < 0) || !ep_tx_ready(0))
        return;

    len = min_t(uint32_t, ep0.tx.todo, 64);
    usb_write(0, ep0.tx.p, len);

    if ((ep0.tx.todo -= len) == 0)
        ep0.tx.todo = -1;
    ep0.tx.p += len;
}

static void usb_start_write_ep0(const void *buf, uint32_t len)
{
    ep0.tx.p = buf;
    ep0.tx.todo = len;
    usb_continue_write_ep0();
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
    bool_t in;

    in = !!(ep & 0x80);
    ep &= 0x7f;

    old_epr = usb->epr[ep];

    /* Sets: Type and Endpoint Address.
     * Clears: CTR_RX and CTR_TX. */
    new_epr = USB_EPR_EP_TYPE(type) | USB_EPR_EA(ep);

    if (in || (ep == 0)) {
        usb_bufd[ep].addr_tx = buf_end;
        buf_end += size;
        usb_bufd[ep].count_tx = 0;
        /* TX: Clears data toggle and sets status to NAK. */
        new_epr |= (old_epr & 0x0070) ^ USB_EPR_STAT_TX(USB_STAT_NAK);
        /* IN Endpoint is immediately ready to transmit. */
        _ep_tx_ready[ep] = TRUE;
    }

    if (!in) {
        usb_bufd[ep].addr_rx = buf_end;
        buf_end += size;
        usb_bufd[ep].count_rx = 0x8400; /* 64 bytes */
        /* RX: Clears data toggle and sets status to VALID. */
        new_epr |= (old_epr & 0x7000) ^ USB_EPR_STAT_RX(USB_STAT_VALID);
        /* OUT Endpoint must wait for a packet from the Host. */
        _ep_rx_ready[ep] = FALSE;
    }

    usb->epr[ep] = new_epr;
}

static void handle_reset(void)
{
    /* Reinitialise floppy subsystem. */
    floppy_reset();

    /* All Endpoints in invalid Tx/Rx state. */
    memset(_ep_rx_ready, 0, sizeof(_ep_rx_ready));
    memset(_ep_tx_ready, 0, sizeof(_ep_tx_ready));

    /* Clear any in-progress Control Transfer. */
    ep0.data_len = -1;
    ep0.tx.todo = -1;

    /* Prepare for Enumeration: Set up Endpoint 0 at Address 0. */
    pending_addr = 0;
    buf_end = 64;
    usb_configure_ep(0, USB_EP_TYPE_CONTROL, 64);
    usb->daddr = USB_DADDR_EF | USB_DADDR_ADD(0);
    usb->istr &= ~USB_ISTR_RESET;
}

static void handle_rx_transfer(uint8_t ep)
{
    uint16_t epr;
    bool_t ready;

    /* Clear CTR_RX. */
    epr = usb->epr[ep];
    epr &= 0x070f;
    epr |= 0x0080;
    usb->epr[ep] = epr;
    _ep_rx_ready[ep] = TRUE;

    /* We only handle Control Transfers here (endpoint 0). */
    if (ep != 0)
        return;

    ready = FALSE;
    epr = usb->epr[ep];

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
        usb_start_write_ep0(ep0.data, ep0.data_len);

    } else {

        /* OUT Control Transfer: Send Status to Host. */
        usb_start_write_ep0(NULL, 0);
        ep0.data_len = -1; /* Complete */

    }
}

static void handle_tx_transfer(uint8_t ep)
{
    uint16_t epr;

    /* Clear CTR_TX. */
    epr = usb->epr[ep];
    epr &= 0x070f;
    epr |= 0x8000;
    usb->epr[ep] = epr;
    _ep_tx_ready[ep] = TRUE;

    /* We only handle Control Transfers here (endpoint 0). */
    if (ep != 0)
        return;

    usb_continue_write_ep0();

    if (pending_addr) {
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
