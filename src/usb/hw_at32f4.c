/*
 * hw_at32f4.c
 * 
 * AT32F4xx-specific handling for USB controller.
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

#include "hw_dwc_otg.h"

static const struct usb_driver *drv;

void hw_usb_init(void)
{
    switch (at32f4_series) {

    case AT32F403:
        drv = &usbd;
        break;

    case AT32F415:
        drv = &dwc_otg;

        conf_iface = IFACE_FS;

        rcc->ahbenr |= RCC_AHBENR_OTGFSEN;

        /* PHY selection must be followed by a core reset. */
        core_reset();
        /* Activate FS transceiver. */
        otg->gccfg = OTG_GCCFG_PWRDWN | OTG_GCCFG_VBUSBSEN;
        break;

    }

    drv->init();
}

void hw_usb_deinit(void)
{
    drv->deinit();

    switch (at32f4_series) {
    case AT32F415:
        rcc->ahbenr &= ~RCC_AHBENR_OTGFSEN;
        break;
    }
}

bool_t hw_has_highspeed(void)
{
    return drv->has_highspeed();
}

bool_t usb_is_highspeed(void)
{
    return drv->is_highspeed();
}

int ep_rx_ready(uint8_t epnr)
{
    return drv->ep_rx_ready(epnr);
}

bool_t ep_tx_ready(uint8_t epnr)
{
    return drv->ep_tx_ready(epnr);
}
 
void usb_read(uint8_t epnr, void *buf, uint32_t len)
{
    drv->read(epnr, buf, len);
}

void usb_write(uint8_t epnr, const void *buf, uint32_t len)
{
    drv->write(epnr, buf, len);
}
 
void usb_stall(uint8_t epnr)
{
    drv->stall(epnr);
}

void usb_configure_ep(uint8_t epnr, uint8_t type, uint32_t size)
{
    switch (at32f4_series) {
    case AT32F403:
        /* Double-buffer hardware implementation is incompatible. */
        if (type == EPT_DBLBUF)
            type = EPT_BULK;
        break;
    }

    drv->configure_ep(epnr, type, size);
}

void usb_setaddr(uint8_t addr)
{
    drv->setaddr(addr);
}

void usb_process(void)
{
    drv->process();
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
