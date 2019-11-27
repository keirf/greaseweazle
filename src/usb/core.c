/*
 * core.c
 * 
 * USB core.
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

struct ep0 ep0;

static bool_t handle_control_request(void)
{
    struct usb_device_request *req = &ep0.req;
    bool_t handled = TRUE;

    if (ep0_data_out() && (req->wLength > sizeof(ep0.data))) {

        WARN("Ctl OUT too long: %u>%u\n", req->wLength, sizeof(ep0.data));
        handled = FALSE;

    } else if ((req->bmRequestType == 0x80)
               && (req->bRequest == GET_DESCRIPTOR)) {

        uint8_t type = req->wValue >> 8;
        uint8_t idx = req->wValue;
        if ((type == DESC_DEVICE) && (idx == 0)) {
            ep0.data_len = device_descriptor[0]; /* bLength */
            memcpy(ep0.data, device_descriptor, ep0.data_len);
        } else if ((type == DESC_CONFIGURATION) && (idx == 0)) {
            ep0.data_len = config_descriptor[2]; /* wTotalLength */
            memcpy(ep0.data, config_descriptor, ep0.data_len);
        } else if ((type == DESC_STRING) && (idx < NR_STRING_DESC)) {
            const char *s = string_descriptors[idx];
            uint16_t *odat = (uint16_t *)ep0.data;
            int i = 0;
            if (idx == 0) {
                odat[i++] = 4+(DESC_STRING<<8);
                memcpy(&odat[i++], s, 2);
            } else {
                odat[i++] = (1+strlen(s))*2+(DESC_STRING<<8);
                while (*s)
                    odat[i++] = *s++;
            }
            ep0.data_len = i*2;
        } else {
            WARN("[Unknown descriptor %u,%u]\n", type, idx);
            handled = FALSE;
        }

    } else if ((req->bmRequestType == 0x00)
               && (req->bRequest == SET_ADDRESS)) {

        usb_setaddr(req->wValue & 0x7f);

    } else if ((req->bmRequestType == 0x00)
              && (req->bRequest == SET_CONFIGURATION)) {

        handled = cdc_acm_set_configuration();

    } else if ((req->bmRequestType&0x7f) == 0x21) {

        handled = cdc_acm_handle_class_request();

    } else {

        uint8_t *pkt = (uint8_t *)req;
        int i;
        WARN("(%02x %02x %02x %02x %02x %02x %02x %02x)",
               pkt[0], pkt[1], pkt[2], pkt[3],
               pkt[4], pkt[5], pkt[6], pkt[7]);
        if (ep0_data_out()) {
            WARN("[");
            for (i = 0; i < ep0.data_len; i++)
                WARN("%02x ", ep0.data[i]);
            WARN("]");
        }
        WARN("\n");
        handled = FALSE;

    }

    if (ep0_data_in() && (ep0.data_len > req->wLength))
        ep0.data_len = req->wLength;

    return handled;
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

void handle_rx_ep0(bool_t is_setup)
{
    bool_t ready = FALSE;
    uint8_t ep = 0;

    if (is_setup) {

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
        uint32_t len = ep_rx_ready(ep);
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

void handle_tx_ep0(void)
{
    usb_write_ep0();
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
