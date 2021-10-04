/*
 * at32f4/stm32.c
 * 
 * Core and peripheral registers.
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

unsigned int FLASH_PAGE_SIZE = 2048;
unsigned int at32f4_series;

unsigned int flash_kb;
unsigned int sram_kb;

static void clock_init(void)
{
    uint32_t cfgr;
    int i;

    if (at32f4_series == AT32F415) {
        /* Flash controller: reads require 4 wait states at 144MHz. */
        flash->acr = FLASH_ACR_PRFTBE | FLASH_ACR_LATENCY(4);
    }

    /* Start up the external oscillator. */
    if (board_config->hse_byp)
        rcc->cr |= RCC_CR_HSEBYP;
    rcc->cr |= RCC_CR_HSEON;

    /* Wait up to approximately one second for the oscillator to start. 
     * If it doesn't start, we indicate this via the status LED. */
    i = 0;
    while (!(rcc->cr & RCC_CR_HSERDY)) {
        early_delay_ms(1);
        if (i++ >= 1000)
            early_fatal(3);
    }

    /* PLLs, scalers, muxes. */
    cfgr = (RCC_CFGR_PLLMUL_18 |        /* PLL = 18*8MHz = 144MHz */
            RCC_CFGR_USBPSC_3 |         /* USB = 144/3MHz = 48MHz */
            RCC_CFGR_PLLSRC_PREDIV1 |
            RCC_CFGR_ADCPRE_DIV8 |
            RCC_CFGR_APB2PSC_2 |        /* APB2 = 144/2MHz = 72MHz */
            RCC_CFGR_APB1PSC_2);        /* APB1 = 144/2MHz = 72MHz */

    if (board_config->hse_mhz == 16)
        cfgr |= RCC_CFGR_HSE_PREDIV2;

    switch (at32f4_series) {
    case AT32F403:
        cfgr |= RCC_CFGR_PLLRANGE_GT72MHZ;
        early_delay_ms(2);
        break;
    case AT32F415: {
        uint32_t rcc_pll = *RCC_PLL;
        rcc_pll &= ~(RCC_PLL_PLLCFGEN | RCC_PLL_FREF_MASK);
        rcc_pll |= RCC_PLL_FREF_8M;
        *RCC_PLL = rcc_pll;
        break;
    }
    }

    rcc->cfgr = cfgr;

    /* Enable and stabilise the PLL. */
    rcc->cr |= RCC_CR_PLLON;
    while (!(rcc->cr & RCC_CR_PLLRDY))
        cpu_relax();

    switch (at32f4_series) {
    case AT32F403:
        early_delay_us(200);
        break;
    case AT32F415:
        *RCC_MISC2 |= RCC_MISC2_AUTOSTEP_EN;
        break;
    }

    /* Switch to the externally-driven PLL for system clock. */
    rcc->cfgr |= RCC_CFGR_SW_PLL;
    while ((rcc->cfgr & RCC_CFGR_SWS_MASK) != RCC_CFGR_SWS_PLL)
        cpu_relax();

    switch (at32f4_series) {
    case AT32F403:
        early_delay_us(200);
        break;
    case AT32F415:
        *RCC_MISC2 &= ~RCC_MISC2_AUTOSTEP_EN;
        break;
    }

    /* Internal oscillator no longer needed. */
    rcc->cr &= ~RCC_CR_HSION;
}

static void peripheral_init(void)
{
    /* Enable basic GPIO and AFIO clocks, and DMA. */
    rcc->apb1enr = 0;
    rcc->apb2enr = (RCC_APB2ENR_IOPAEN |
                    RCC_APB2ENR_IOPBEN |
                    RCC_APB2ENR_IOPCEN |
                    RCC_APB2ENR_IOPFEN |
                    RCC_APB2ENR_AFIOEN);
    rcc->ahbenr = RCC_AHBENR_DMA1EN;

    /* Reclaim JTAG pins. */
    afio->mapr = AFIO_MAPR_SWJ_ON_JTAG_OFF;
    gpio_configure_pin(gpioa, 15, GPI_floating);
    gpio_configure_pin(gpiob,  3, GPI_floating);
    gpio_configure_pin(gpiob,  4, GPI_floating);
}

static void identify_mcu(void)
{
    flash_kb = *(uint16_t *)0x1ffff7e0;
    if (flash_kb <= 128)
        FLASH_PAGE_SIZE = 1024;

    at32f4_series = *(uint8_t *)0x1ffff7f3; /* UID[95:88] */
    switch (at32f4_series) {
    case AT32F403:
        sram_kb = 96;
        break;
    case AT32F415:
        sram_kb = 32;
        break;
    default:
        early_fatal(4);
    }
}

void stm32_init(void)
{
    cortex_init();
    identify_mcu();
    identify_board_config();
    clock_init();
    peripheral_init();
    cpu_sync();
}

void gpio_configure_pin(GPIO gpio, unsigned int pin, unsigned int mode)
{
    gpio_write_pin(gpio, pin, mode >> 4);
    mode &= 0xfu;
    if (pin >= 8) {
        pin -= 8;
        gpio->crh = (gpio->crh & ~(0xfu<<(pin<<2))) | (mode<<(pin<<2));
    } else {
        gpio->crl = (gpio->crl & ~(0xfu<<(pin<<2))) | (mode<<(pin<<2));
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
