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
uint8_t pending_addr;

bool_t handle_control_request(void)
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

        pending_addr = req->wValue & 0x7f;

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

/*
 * Local variables:
 * mode: C
 * c-file-style: "Linux"
 * c-basic-offset: 4
 * tab-width: 4
 * indent-tabs-mode: nil
 * End:
 */
