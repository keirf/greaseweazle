/*
 * cdc_acm.c
 * 
 * USB CDC ACM handling (Communications Device Class, Abstract Control Model).
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

#define TRACE 1

/* CDC Communications Class requests */
#define CDC_SET_LINE_CODING 0x20
#define CDC_GET_LINE_CODING 0x21
#define CDC_SET_CONTROL_LINE_STATE 0x22
#define CDC_SEND_BREAK 0x23

static struct packed line_coding {
    uint32_t baud;
    uint8_t nr_stop;
    uint8_t parity;
    uint8_t nr_data;
} line_coding = { 
    .baud = 9600,
    .nr_stop = 0,
    .parity = 0,
    .nr_data = 8 };

#if TRACE
#define TRC printk
#else
static inline void TRC(const char *format, ...) { }
#endif

static void dump_line_coding(const struct line_coding *lc)
{
    int parity = (lc->parity > 4) ? 5 : lc->parity;

    TRC("%u,%u%c%s\n", lc->baud, lc->nr_data,
        "noems?"[parity],
        (lc->nr_stop == 0) ? "1"
        : (lc->nr_stop == 1) ? "1.5"
        : (lc->nr_stop == 2) ? "2" : "X");
}

bool_t cdc_acm_handle_class_request(void)
{
    struct usb_device_request *req = &ep0.req;
    bool_t handled = TRUE;

    switch (req->bRequest) {

    case CDC_SET_LINE_CODING: {
        struct line_coding *lc = (struct line_coding *)ep0.data;
        TRC("SET_LINE_CODING: ");
        dump_line_coding(lc);
        if (line_coding.baud != lc->baud) {
            switch (lc->baud) {
            case BAUD_CLEAR_COMMS:
                usb_cdc_acm_ops.configure();
                printk("Comms Line Cleared\n");
                break;
            }
        }
        line_coding = *lc;
        break;
    }

    case CDC_GET_LINE_CODING: {
        struct line_coding *lc = (struct line_coding *)ep0.data;
        TRC("GET_LINE_CODING: ");
        *lc = line_coding;
        dump_line_coding(lc);
        ep0.data_len = sizeof(*lc);
        break;
    }

    case CDC_SET_CONTROL_LINE_STATE:
        /* wValue = DTR/RTS. We ignore them and return success. */
        break;

    case CDC_SEND_BREAK:
        /* wValue = #millisecs. We ignore it and return success. */
        TRC("BREAK\n");
        usb_cdc_acm_ops.reset();
        usb_cdc_acm_ops.configure();
        break;

    default:
        WARN("[Class-specific: %02x]\n", req->bRequest);
        handled = FALSE;
        break;

    }

    return handled;
}

bool_t cdc_acm_set_configuration(void)
{
    uint8_t bulk_type = USB_EP_TYPE_BULK_DBLBUF;

#ifdef BOOTLOADER
    /* We don't bother with the complicated double-buffered endpoints. The 
     * regular bulk endpoints are fast enough and possibly more reliable. */
    bulk_type = USB_EP_TYPE_BULK;
#endif

    /* Notification Element (D->H) */
    usb_configure_ep(0x81, USB_EP_TYPE_INTERRUPT, 0);
    /* Bulk Pipe (H->D) */
    usb_configure_ep(0x02, bulk_type, USB_FS_MPS);
    /* Bulk Pipe (D->H) */
    usb_configure_ep(0x83, bulk_type, USB_FS_MPS);

    usb_cdc_acm_ops.configure();

    return TRUE;
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
