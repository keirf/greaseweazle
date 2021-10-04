/*
 * f1/stm32.c
 * 
 * Core and peripheral registers.
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

unsigned int flash_kb;
unsigned int sram_kb;

static void clock_init(void)
{
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
}

static void gpio_init(GPIO gpio)
{
    /* Floating Input. Reference Manual states that JTAG pins are in PU/PD
     * mode at reset, so ensure all PU/PD are disabled. */
    gpio->crl = gpio->crh = 0x44444444u;
}

static void peripheral_init(void)
{
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

    /* Turn off serial-wire JTAG and reclaim the GPIOs.
     * We cannot use SW-DP because we use PA14 for entering firmware-update
     * mode, and that requires us to disable SW-DP and enable PA14 pull up.
     * After SW-DP is disabled it seems impossible to re-enable until reset. */
    afio->mapr = AFIO_MAPR_SWJ_CFG_DISABLED;

    /* All pins in a stable state. */
    gpio_init(gpioa);
    gpio_init(gpiob);
    gpio_init(gpioc);
}

static void identify_mcu(void)
{
    flash_kb = *(volatile uint16_t *)0x1ffff7e0;
    switch (flash_kb) {
    case 16: sram_kb =  6; break; /* STM31F103x4 Low Density */
    case 32: sram_kb = 10; break; /* STM32F103x6 Low Density */
    default: sram_kb = 20; break; /* STM32F103xx Medium Density */
    }
}

void stm32_init(void)
{
    cortex_init();
    identify_mcu();
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
