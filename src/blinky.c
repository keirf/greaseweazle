/*
 * blinky.c
 * 
 * LED blink test to validate STM32F103C8 chips. This test will find
 * remarked and cloned low-density devices with:
 *  - Less than 20kB RAM
 *  - Less than 64kB Flash
 *  - Missing peripherals TIM1-4, I2C1-2, SPI1-2
 * 
 * As the LED blinks, a character is written to USART1 at 9600 baud (8n1).
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

int EXC_reset(void) __attribute__((alias("main")));

void IRQ_30(void) __attribute__((alias("IRQ_tim4")));
#define IRQ_TIM4 30

#ifndef NDEBUG
/* Keep the linker happy. */
int printk(const char *format, ...) { return 0; }
#endif

static void IRQ_tim4(void)
{
    static bool_t x;

    /* Quiesce the IRQ source. */
    tim4->sr = 0;

    /* Blink the LED. */
    gpio_write_pin(gpiob, 12, x);
    gpio_write_pin(gpioc, 13, x);
    x ^= 1;

    /* Write to the serial line. */
    usart1->dr = '.';
}

/* Pseudorandom LFSR. */
static uint32_t srand = 0x87a2263c;
static uint32_t rand(void)
{
    uint32_t x = srand;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    srand = x;
    return x;
}

int main(void)
{
    uint32_t fp, *p;
    int i;

    /* Relocate DATA. Initialise BSS. */
    if (_sdat != _ldat)
        memcpy(_sdat, _ldat, _edat-_sdat);
    memset(_sbss, 0, _ebss-_sbss);

    stm32_init();

    /* Configure USART1: 9600,8n1. */
    rcc->apb2enr |= RCC_APB2ENR_USART1EN;
    gpio_configure_pin(gpioa, 9, AFO_pushpull(_10MHz));
    gpio_configure_pin(gpioa, 10, GPI_pull_up);
    usart1->brr = SYSCLK / 9600;
    usart1->cr1 = (USART_CR1_UE | USART_CR1_TE | USART_CR1_RE);

    /* Configure LED pin(s). LED is connected to VDD. */
    gpio_configure_pin(gpiob, 12, GPO_opendrain(_2MHz, HIGH));
    gpio_configure_pin(gpioc, 13, GPO_opendrain(_2MHz, HIGH));

    /* Touch I2C peripherals. */
    rcc->apb1enr |= RCC_APB1ENR_I2C1EN;
    i2c1->oar1 = i2c1->oar2 = 0x26;
    if ((i2c1->oar1 != 0x26) || (i2c1->oar2 != 0x26))
        goto fail;
    rcc->apb1enr |= RCC_APB1ENR_I2C2EN;
    i2c2->oar1 = i2c2->oar2 = 0x26;
    if ((i2c2->oar1 != 0x26) || (i2c2->oar2 != 0x26))
        goto fail;

    /* Touch SPI peripherals. */
    rcc->apb2enr |= RCC_APB2ENR_SPI1EN;
    rcc->apb1enr |= RCC_APB1ENR_SPI2EN;
    spi1->cr2 = spi2->cr2 = 3;
    if ((spi1->cr2 != 3) || (spi2->cr2 != 3))
        goto fail;

    /* Touch TIM peripherals. */
    tim1->arr = tim2->arr = tim3->arr = 123;
    if ((tim1->arr != 123) || (tim2->arr != 123) | (tim3->arr != 123))
        goto fail;

    /* Configure TIM4 to overflow at 2Hz. */
    tim4->psc = sysclk_us(100)-1;
    tim4->arr = 5000-1;
    tim4->dier = TIM_DIER_UIE;
    tim4->cr2 = 0;
    tim4->cr1 = TIM_CR1_URS | TIM_CR1_CEN;

    /* Enable TIM4 IRQ, to be triggered at 2Hz. */
    IRQx_set_prio(IRQ_TIM4, TIMER_IRQ_PRI);
    IRQx_clear_pending(IRQ_TIM4);
    IRQx_enable(IRQ_TIM4);

    /* Erase and write the last page of Flash below 64kB. Check it reads 
     * back okay. */
    fpec_init();
    fp = (uint32_t)(_stext + 64*1024 - FLASH_PAGE_SIZE);
    fpec_page_erase(fp);
    memset(_ebss, 0xff, FLASH_PAGE_SIZE);
    if (memcmp((void *)fp, _ebss, FLASH_PAGE_SIZE))
        goto fail; /* didn't erase ok */
    p = (uint32_t *)_ebss;
    for (i = 0; i < FLASH_PAGE_SIZE/4; i++)
        *p++ = rand();
    fpec_write(_ebss, FLASH_PAGE_SIZE, fp);
    if (memcmp((void *)fp, _ebss, FLASH_PAGE_SIZE))
        goto fail; /* didn't write ok */

    /* Endlessly test SRAM by filling with pseudorandom junk and then 
     * testing the values read back okay. */
    for (;;) {
        uint32_t *p = (uint32_t *)_ebss, sr = srand;
        while (p < (uint32_t *)(0x20000000 + 20*1024))
            *p++ = rand();
        srand = sr;
        p = (uint32_t *)_ebss;
        while (p < (uint32_t *)(0x20000000 + 20*1024))
            if (*p++ != rand())
                goto fail;
    }

fail:
    /* On SRAM failure we light the LED(s) and hang. */
    IRQ_global_disable();
    gpio_write_pin(gpiob, 12, LOW);
    gpio_write_pin(gpioc, 13, LOW);
    for (;;) ;

    return 0;
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
