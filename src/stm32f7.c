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

/* XXX */
void floppy_init(void) {}
void floppy_process(void) {}
void usb_init(void) {}
void usb_process(void) {}
void fpec_init(void) {}
void fpec_page_erase(uint32_t flash_address) {}
void fpec_write(const void *data, unsigned int size, uint32_t flash_address) {}
void usb_read(uint8_t ep, void *buf, uint32_t len) {}
void usb_write(uint8_t ep, const void *buf, uint32_t len) {}
bool_t ep_tx_ready(uint8_t ep) { return FALSE; }
int ep_rx_ready(uint8_t ep) { return -1; }

static void clock_init(void)
{
    /* Flash controller: reads require 7 wait states at 216MHz. */
    flash->acr = FLASH_ACR_ARTEN | FLASH_ACR_PRFTEN | FLASH_ACR_LATENCY(7);

    /* Bus divisors. */
    rcc->cfgr = (RCC_CFGR_PPRE2(4) | /* APB2 = 216MHz/2 = 108MHz  */
                 RCC_CFGR_PPRE1(5) | /* APB1 = 216MHz/4 = 54MHz */
                 RCC_CFGR_HPRE(0));  /* AHB  = 216MHz/1 = 216MHz */

    /* Timers run from Host Clock (216MHz). */
    rcc->dckcfgr1 = RCC_DCKCFGR1_TIMPRE;

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

    /* Enable and stabilise the PLL. */
    rcc->cr |= RCC_CR_PLLON;
    while (!(rcc->cr & RCC_CR_PLLRDY))
        cpu_relax();

    /* Switch to the externally-driven PLL for system clock. */
    rcc->cfgr |= RCC_CFGR_SW(2);
    while ((rcc->cfgr & RCC_CFGR_SWS(3)) != RCC_CFGR_SWS(2))
        cpu_relax();

    /* Internal oscillator no longer needed. */
    rcc->cr &= ~RCC_CR_HSION;

    /* Enable SysTick counter at 216MHz/8 = 27MHz. */
    stk->load = STK_MASK;
    stk->ctrl = STK_CTRL_ENABLE;
}

void peripheral_clock_delay(void)
{
    delay_ticks(2);
}

static void peripheral_init(void)
{
    /* Enable basic GPIO clocks, DTCM RAM, and DMA. */
    rcc->ahb1enr = (RCC_AHB1ENR_DMA2EN |
                    RCC_AHB1ENR_DMA1EN |
                    RCC_AHB1ENR_DTCMRAMEN |
                    RCC_AHB1ENR_GPIOCEN |
                    RCC_AHB1ENR_GPIOBEN | 
                    RCC_AHB1ENR_GPIOAEN);
    peripheral_clock_delay();

    /* Release JTAG pins. */
    gpio_configure_pin(gpioa, 15, GPI_floating);
    gpio_configure_pin(gpiob,  3, GPI_floating);
    gpio_configure_pin(gpiob,  4, GPI_floating);
}

void stm32_init(void)
{
    cortex_init();
    clock_init();
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

/*
 * Local variables:
 * mode: C
 * c-file-style: "Linux"
 * c-basic-offset: 4
 * tab-width: 4
 * indent-tabs-mode: nil
 * End:
 */
