/*
 * hw_at32f415.c
 * 
 * AT32F415-specific handling for DWC-OTG USB 2.0 controller.
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

#include "hw_dwc_otg.h"

void hw_usb_init(void)
{
    conf_iface = IFACE_FS;

    rcc->ahbenr |= RCC_AHBENR_OTGFSEN;

    /* PHY selection must be followed by a core reset. */
    core_reset();
    /* Activate FS transceiver. */
    otg->gccfg = OTG_GCCFG_PWRDWN | OTG_GCCFG_VBUSBSEN;

    dwc_otg.init();
}

void hw_usb_deinit(void)
{
    dwc_otg.deinit();

    rcc->ahbenr &= ~RCC_AHBENR_OTGFSEN;
}

bool_t hw_has_highspeed(void)
{
    return dwc_otg.has_highspeed();
}

bool_t usb_is_highspeed(void)
{
    return dwc_otg.is_highspeed();
}

int ep_rx_ready(uint8_t epnr)
{
    return dwc_otg.ep_rx_ready(epnr);
}

bool_t ep_tx_ready(uint8_t epnr)
{
    return dwc_otg.ep_tx_ready(epnr);
}
 
void usb_read(uint8_t epnr, void *buf, uint32_t len)
{
    dwc_otg.read(epnr, buf, len);
}

void usb_write(uint8_t epnr, const void *buf, uint32_t len)
{
    dwc_otg.write(epnr, buf, len);
}
 
void usb_stall(uint8_t epnr)
{
    dwc_otg.stall(epnr);
}

void usb_configure_ep(uint8_t epnr, uint8_t type, uint32_t size)
{
    dwc_otg.configure_ep(epnr, type, size);
}

void usb_setaddr(uint8_t addr)
{
    dwc_otg.setaddr(addr);
}

void usb_process(void)
{
    dwc_otg.process();
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
