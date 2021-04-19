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

    dwc_otg_init();
}

void hw_usb_deinit(void)
{
    dwc_otg_deinit();

    rcc->ahbenr &= ~RCC_AHBENR_OTGFSEN;
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
