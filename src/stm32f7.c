/*
 * stm32f7.c
 * 
 * Core and peripheral registers.
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

uint8_t board_id;

#define early_delay_ms(ms) (delay_ticks((ms)*2000))
#define early_delay_us(ms) (delay_ticks((ms)*2))

/* Blink the activity LED to indicate fatal error. */
static void early_fatal(int blinks) __attribute__((noreturn));
static void early_fatal(int blinks)
{
    int i;
    rcc->ahb1enr |= RCC_AHB1ENR_GPIOBEN;
    delay_ticks(10);
    gpio_configure_pin(gpiob, 13, GPO_pushpull(IOSPD_LOW, HIGH));
    for (;;) {
        for (i = 0; i < blinks; i++) {
            gpio_write_pin(gpiob, 13, LOW);
            early_delay_ms(150);
            gpio_write_pin(gpiob, 13, HIGH);
            early_delay_ms(150);
        }
        early_delay_ms(2000);
    }
}

static void board_id_init(void)
{
    uint16_t low, high;
    uint8_t id = 0;
    int i;

    rcc->ahb1enr |= RCC_AHB1ENR_GPIOCEN;
    early_delay_us(2);

    /* Pull PC[15:13] low, and check which are tied HIGH. */
    for (i = 0; i < 3; i++)
        gpio_configure_pin(gpioc, 13+i, GPI_pull_down);
    early_delay_us(10);
    high = (gpioc->idr >> 13) & 7;

    /* Pull PC[15:13] high, and check which are tied LOW. */
    for (i = 0; i < 3; i++)
        gpio_configure_pin(gpioc, 13+i, GPI_pull_up);
    early_delay_us(10);
    low = (~gpioc->idr >> 13) & 7;

    /* Each PCx pin defines a 'trit': 0=float, 1=low, 2=high. 
     * We build a 3^3 ID space from the resulting three-trit ID. */
    for (i = 0; i < 3; i++) {
        id *= 3;
        switch ((high>>1&2) | (low>>2&1)) {
        case 0: break;          /* float = 0 */
        case 1: id += 1; break; /* LOW   = 1 */
        case 2: id += 2; break; /* HIGH  = 2 */
        case 3: early_fatal(1); /* cannot be tied HIGH *and* LOW! */
        }
        high <<= 1;
        low <<= 1;
    }

    /* Panic if the ID is unrecognised. */
    board_id = id;
    if (board_id != 0)
        early_fatal(2);
}

static void clock_init(void)
{
    /* Disable all peripheral clocks except the essentials before enabling 
     * Over-drive mode (see note in RM0431, p102). We still need access to RAM
     * and to the power interface itself. */
    rcc->ahb1enr = RCC_AHB1ENR_DTCMRAMEN;
    rcc->apb1enr = RCC_APB1ENR_PWREN;
    early_delay_us(2);

    /* Start up the external oscillator. */
    rcc->cr |= RCC_CR_HSEON;
    while (!(rcc->cr & RCC_CR_HSERDY))
        cpu_relax();

    /* Main PLL. */
    rcc->pllcfgr = (RCC_PLLCFGR_PLLSRC_HSE | /* PLLSrc = HSE = 8MHz */
                    RCC_PLLCFGR_PLLM(4) |    /* PLL In = HSE/4 = 2MHz */
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
    board_id_init();
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
