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
#if 0
    /* Flash controller: reads require 2 wait states at 72MHz. */
    flash->acr = FLASH_ACR_PRFTBE | FLASH_ACR_LATENCY(2);

    /* Start up the external oscillator. */
    rcc->cr |= RCC_CR_HSEON;
    while (!(rcc->cr & RCC_CR_HSERDY))
        cpu_relax();

    /* PLLs, scalers, muxes. */
    rcc->cfgr = (RCC_CFGR_PLLMUL(9) |        /* PLL = 9*8MHz = 72MHz */
                 RCC_CFGR_PLLSRC_PREDIV1 |
                 RCC_CFGR_ADCPRE_DIV8 |
                 RCC_CFGR_PPRE1_DIV2);

    /* Enable and stabilise the PLL. */
    rcc->cr |= RCC_CR_PLLON;
    while (!(rcc->cr & RCC_CR_PLLRDY))
        cpu_relax();

    /* Switch to the externally-driven PLL for system clock. */
    rcc->cfgr |= RCC_CFGR_SW_PLL;
    while ((rcc->cfgr & RCC_CFGR_SWS_MASK) != RCC_CFGR_SWS_PLL)
        cpu_relax();

    /* Internal oscillator no longer needed. */
    rcc->cr &= ~RCC_CR_HSION;

    /* Enable SysTick counter at 72/8=9MHz. */
    stk->load = STK_MASK;
    stk->ctrl = STK_CTRL_ENABLE;
#endif
}

static void gpio_init(GPIO gpio)
{
    /* Floating Input. Reference Manual states that JTAG pins are in PU/PD
     * mode at reset, so ensure all PU/PD are disabled. */
    //gpio->crl = gpio->crh = 0x44444444u;
}

static void peripheral_init(void)
{
#if 0
    /* Enable basic GPIO and AFIO clocks, all timers, and DMA. */
    rcc->apb1enr = (RCC_APB1ENR_TIM2EN |
                    RCC_APB1ENR_TIM3EN |
                    RCC_APB1ENR_TIM4EN);
    rcc->apb2enr = (RCC_APB2ENR_IOPAEN |
                    RCC_APB2ENR_IOPBEN |
                    RCC_APB2ENR_IOPCEN |
                    RCC_APB2ENR_AFIOEN |
                    RCC_APB2ENR_TIM1EN);
    rcc->ahbenr = RCC_AHBENR_DMA1EN;

    /* Turn off serial-wire JTAG and reclaim the GPIOs. */
    afio->mapr = AFIO_MAPR_SWJ_CFG_DISABLED;
#endif

    /* All pins in a stable state. */
    gpio_init(gpioa);
    gpio_init(gpiob);
    gpio_init(gpioc);
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
