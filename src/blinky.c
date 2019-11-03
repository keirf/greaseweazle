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

#define FLASH_KB 64
#define SRAM_KB  20

int EXC_reset(void) __attribute__((alias("main")));

void IRQ_30(void) __attribute__((alias("IRQ_tim4")));
#define IRQ_TIM4 30

static void FAIL(void)
{
    /* Light the LED(s) and hang. */
    IRQ_global_disable();
    printk("FAILED\n");
    gpio_write_pin(gpiob, 12, LOW);
    gpio_write_pin(gpioc, 13, LOW);
    for (;;) ;
}

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
    printk(".");
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

static void i2c_test(I2C i2c, int nr)
{
    printk("Testing I2C%d... ", nr);
    i2c->cr1 = 0;
    i2c->oar1 = 0x10;
    i2c->cr2 = (I2C_CR2_FREQ(36) |
                I2C_CR2_ITERREN |
                I2C_CR2_ITEVTEN |
                I2C_CR2_ITBUFEN);
    i2c->cr1 = I2C_CR1_ACK | I2C_CR1_PE;
    if ((i2c->oar1 != 0x10) || (i2c->cr1 != (I2C_CR1_ACK | I2C_CR1_PE)))
        FAIL();
    printk("Done\n");
}

static void spi_test(SPI spi, int nr)
{
    printk("Testing SPI%d... ", nr);
    spi->cr2 = (SPI_CR2_TXDMAEN | SPI_CR2_RXDMAEN);
    spi->cr1 = (SPI_CR1_MSTR | /* master */
                SPI_CR1_SSM | SPI_CR1_SSI | /* software NSS */
                SPI_CR1_SPE | /* enable */
                SPI_CR1_DFF | /* 16-bit */
                SPI_CR1_CPHA |
                SPI_CR1_BR_DIV4);
    if (spi->cr2 != (SPI_CR2_TXDMAEN | SPI_CR2_RXDMAEN))
        FAIL();
    printk("Done\n");
}

static void tim_test(TIM tim, int nr)
{
    /* Configure to overflow at 2Hz. */
    printk("Testing TIM%d... ", nr);
    tim->psc = sysclk_us(100)-1;
    tim->arr = 5000-1;
    tim->dier = TIM_DIER_UIE;
    tim->cr2 = 0;
    tim->cr1 = TIM_CR1_URS | TIM_CR1_CEN;
    if (tim->arr != (5000-1))
        FAIL();
    printk("Done\n");
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
    console_init();

    printk("\n** Blinky Test **\n");
    printk("** Keir Fraser <keir.xen@gmail.com>\n");
    printk("** https://github.com/keirf/Greaseweazle\n");

    /* Configure LED pin(s). LED is connected to VDD. */
    gpio_configure_pin(gpiob, 12, GPO_opendrain(_2MHz, HIGH));
    gpio_configure_pin(gpioc, 13, GPO_opendrain(_2MHz, HIGH));

    /* Test I2C peripherals. */
    rcc->apb1enr |= RCC_APB1ENR_I2C1EN;
    i2c_test(i2c1, 1);
    rcc->apb1enr |= RCC_APB1ENR_I2C2EN;
    i2c_test(i2c2, 2);

    /* Test SPI peripherals. */
    rcc->apb2enr |= RCC_APB2ENR_SPI1EN;
    spi_test(spi1, 1);
    rcc->apb1enr |= RCC_APB1ENR_SPI2EN;
    spi_test(spi2, 2);

    /* Test TIM peripherals, set up to overflow at 2Hz. */
    tim_test(tim1, 1);
    tim_test(tim2, 2);
    tim_test(tim3, 3);
    tim_test(tim4, 4);

    /* Enable TIM4 IRQ, to be triggered at 2Hz. */
    printk("Testing TIM4 IRQ... ");
    IRQx_set_prio(IRQ_TIM4, TIMER_IRQ_PRI);
    IRQx_clear_pending(IRQ_TIM4);
    IRQx_enable(IRQ_TIM4);
    printk("Enabled\n");

    /* Erase and write the last page of Flash below 64kB. Check it reads 
     * back okay. */
    printk("Testing %ukB Flash... ", FLASH_KB);
    fpec_init();
    fp = (uint32_t)(_stext + FLASH_KB*1024 - FLASH_PAGE_SIZE);
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
    printk("Done\n");

    /* Endlessly test SRAM by filling with pseudorandom junk and then 
     * testing the values read back okay. */
    printk("Testing %ukB SRAM (endless loop)...", SRAM_KB);
    for (;;) {
        uint32_t *p = (uint32_t *)_ebss, sr = srand;
        while (p < (uint32_t *)(0x20000000 + SRAM_KB*1024))
            *p++ = rand();
        srand = sr;
        p = (uint32_t *)_ebss;
        while (p < (uint32_t *)(0x20000000 + SRAM_KB*1024))
            if (*p++ != rand())
                goto fail;
    }

fail:
    FAIL();
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
