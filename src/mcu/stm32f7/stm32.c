/*
 * f7/stm32.c
 * 
 * Core and peripheral registers.
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

unsigned int flash_kb = 64;

static void clock_init(void)
{
    unsigned int hse = board_config->hse_mhz;
    int i;

    /* Disable all peripheral clocks except the essentials before enabling 
     * Over-drive mode (see note in RM0431, p102). We still need access to RAM
     * and to the power interface itself. */
    rcc->ahb1enr = RCC_AHB1ENR_DTCMRAMEN;
    rcc->apb1enr = RCC_APB1ENR_PWREN;
    early_delay_us(2);

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

    /* Main PLL. */
    rcc->pllcfgr = (RCC_PLLCFGR_PLLSRC_HSE | /* PLLSrc = HSE */
                    RCC_PLLCFGR_PLLM(hse/2) |/* PLL In = HSE/(HSE/2) = 2MHz */
                    RCC_PLLCFGR_PLLN(216) |  /* PLLVCO = 2MHz*216 = 432MHz */
                    RCC_PLLCFGR_PLLP(0) |    /* SYSCLK = 432MHz/2 = 216MHz */
                    RCC_PLLCFGR_PLLQ(9));    /* USB    = 432MHz/9 = 48MHz */

    /* Enable the PLL. */
    rcc->cr |= RCC_CR_PLLON;

    /* Enable Over-drive (required for 216MHz operation). */
    pwr->cr1 |= PWR_CR1_ODEN;
    while (!(pwr->csr1 & PWR_CSR1_ODRDY))
        cpu_relax();
    pwr->cr1 |= PWR_CR1_ODSWEN;
    while (!(pwr->csr1 & PWR_CSR1_ODSWRDY))
        cpu_relax();
    
    /* Flash controller: reads require 7 wait states at 216MHz. */
    flash->acr = FLASH_ACR_ARTEN | FLASH_ACR_PRFTEN | FLASH_ACR_LATENCY(7);

    /* Bus divisors. */
    rcc->cfgr = (RCC_CFGR_PPRE2(4) | /* APB2 = 216MHz/2 = 108MHz  */
                 RCC_CFGR_PPRE1(5) | /* APB1 = 216MHz/4 = 54MHz */
                 RCC_CFGR_HPRE(0));  /* AHB  = 216MHz/1 = 216MHz */

    /* Timers run from Host Clock (216MHz). */
    rcc->dckcfgr1 = RCC_DCKCFGR1_TIMPRE;

    /* Wait for the PLL to stabilise. */
    while (!(rcc->cr & RCC_CR_PLLRDY))
        cpu_relax();

    /* Switch to the externally-driven PLL for system clock. */
    rcc->cfgr |= RCC_CFGR_SW(2);
    while ((rcc->cfgr & RCC_CFGR_SWS(3)) != RCC_CFGR_SWS(2))
        cpu_relax();

    /* Internal oscillator no longer needed. */
    rcc->cr &= ~RCC_CR_HSION;
}

void peripheral_clock_delay(void)
{
    delay_ticks(2);
}

static void peripheral_init(void)
{
    /* Enable basic GPIO clocks, DTCM RAM, DMA, and EXTICR. */
    rcc->ahb1enr |= (RCC_AHB1ENR_DMA2EN |
                     RCC_AHB1ENR_DMA1EN |
                     RCC_AHB1ENR_DTCMRAMEN |
                     RCC_AHB1ENR_GPIOCEN |
                     RCC_AHB1ENR_GPIOBEN | 
                     RCC_AHB1ENR_GPIOAEN);
    rcc->apb2enr |= (RCC_APB2ENR_SYSCFGEN);
    peripheral_clock_delay();

    /* Release JTAG pins. */
    gpio_configure_pin(gpioa, 15, GPI_floating);
    gpio_configure_pin(gpiob,  3, GPI_floating);
    gpio_configure_pin(gpiob,  4, GPI_floating);
}

void stm32_init(void)
{
    cortex_init();
    identify_board_config();
    clock_init();
    icache_enable();
    dcache_enable();
    peripheral_init();
    cpu_sync();
}

void gpio_configure_pin(GPIO gpio, unsigned int pin, unsigned int mode)
{
    gpio_write_pin(gpio, pin, mode >> 7);
    gpio->moder = (gpio->moder & ~(3<<(pin<<1))) | ((mode&3)<<(pin<<1));
    mode >>= 2;
    gpio->otyper = (gpio->otyper & ~(1<<pin)) | ((mode&1)<<pin);
    mode >>= 1;
    gpio->ospeedr = (gpio->ospeedr & ~(3<<(pin<<1))) | ((mode&3)<<(pin<<1));
    mode >>= 2;
    gpio->pupdr = (gpio->pupdr & ~(3<<(pin<<1))) | ((mode&3)<<(pin<<1));
}

void gpio_set_af(GPIO gpio, unsigned int pin, unsigned int af)
{
    if (pin < 8) {
        gpio->afrl = (gpio->afrl & ~(15<<(pin<<2))) | (af<<(pin<<2));
    } else {
        pin -= 8;
        gpio->afrh = (gpio->afrh & ~(15<<(pin<<2))) | (af<<(pin<<2));
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
