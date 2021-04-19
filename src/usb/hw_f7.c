/*
 * hw_f7.c
 * 
 * STM32F730-specific handling for DWC-OTG USB 2.0 controller.
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

#include "hw_dwc_otg.h"

static void hsphyc_init(void)
{
    /* Enable the LDO and wait for it to be ready. */
    hsphyc->ldo |= HSPHYC_LDO_ENABLE;
    do { delay_us(1); } while (!(hsphyc->ldo & HSPHYC_LDO_STATUS));

    /* This is correct only for HSE = 16Mhz. */
    hsphyc->pll1 |= HSPHYC_PLL1_SEL(3);

    /* Magic values from the LL driver. We can probably discard them. */
    hsphyc->tune |= (HSPHYC_TUNE_HSDRVCHKITRIM(7) |
                     HSPHYC_TUNE_HSDRVRFRED |
                     HSPHYC_TUNE_HSDRVDCCUR |
                     HSPHYC_TUNE_INCURRINT |
                     HSPHYC_TUNE_INCURREN);

    /* Enable the PLL and wait to stabilise. */
    hsphyc->pll1 |= HSPHYC_PLL1_EN;
    delay_ms(2);
}

void hw_usb_init(void)
{
    /* Determine which PHY we use based on hardware submodel ID. */
    conf_iface = board_config->hs_usb ? IFACE_HS_EMBEDDED : IFACE_FS;

    /*
     * HAL_PCD_MspInit
     */

    switch (conf_port) {
    case PORT_FS:
        ASSERT(conf_iface == IFACE_FS);
        gpio_set_af(gpioa, 11, 10);
        gpio_set_af(gpioa, 12, 10);
        gpio_configure_pin(gpioa, 11, AFO_pushpull(IOSPD_HIGH));
        gpio_configure_pin(gpioa, 12, AFO_pushpull(IOSPD_HIGH));
        rcc->ahb2enr |= RCC_AHB2ENR_OTGFSEN;
        break;
    case PORT_HS:
        ASSERT((conf_iface == IFACE_FS) || (conf_iface == IFACE_HS_EMBEDDED));
        if (conf_iface == IFACE_FS) {
            gpio_set_af(gpiob, 14, 12);
            gpio_set_af(gpiob, 15, 12);
            gpio_configure_pin(gpiob, 14, AFO_pushpull(IOSPD_HIGH));
            gpio_configure_pin(gpiob, 15, AFO_pushpull(IOSPD_HIGH));
            rcc->ahb1enr |= RCC_AHB1ENR_OTGHSEN;
        } else {
            rcc->ahb1enr |= RCC_AHB1ENR_OTGHSEN;
            rcc->ahb1enr |= RCC_AHB1ENR_OTGHSULPIEN;
            rcc->apb2enr |= RCC_APB2ENR_OTGPHYCEN;
        }
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
        /* Disable the FS transceiver, enable the HS transceiver. */
        otg->gccfg &= ~OTG_GCCFG_PWRDWN;
        otg->gccfg |= OTG_GCCFG_PHYHSEN;
        hsphyc_init();
        core_reset();
    }

    dwc_otg_init();
}

void hw_usb_deinit(void)
{
    dwc_otg_deinit();

    /* HAL_PCD_MspDeInit */
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

/*
 * Local variables:
 * mode: C
 * c-file-style: "Linux"
 * c-basic-offset: 4
 * tab-width: 4
 * indent-tabs-mode: nil
 * End:
 */
