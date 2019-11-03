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
#define NR_I2C    2
#define NR_SPI    2
#define NR_TIM    4

int EXC_reset(void) __attribute__((alias("main")));

void IRQ_30(void) __attribute__((alias("IRQ_tim4")));
#define IRQ_TIM4 30

/* All exceptions print a simple report and then hang. */
void EXC_nmi(void) __attribute__((alias("EXC_blinky")));
void EXC_hard_fault(void) __attribute__((alias("EXC_blinky")));
void EXC_memory_management_fault(void) __attribute__((alias("EXC_blinky")));
void EXC_bus_fault(void) __attribute__((alias("EXC_blinky")));
void EXC_usage_fault(void) __attribute__((alias("EXC_blinky")));
void EXC_7(void) __attribute__((alias("EXC_blinky")));
void EXC_8(void) __attribute__((alias("EXC_blinky")));
void EXC_9(void) __attribute__((alias("EXC_blinky")));
void EXC_10(void) __attribute__((alias("EXC_blinky")));
void EXC_sv_call(void) __attribute__((alias("EXC_blinky")));
void EXC_12(void) __attribute__((alias("EXC_blinky")));
void EXC_13(void) __attribute__((alias("EXC_blinky")));
void EXC_pend_sv(void) __attribute__((alias("EXC_blinky")));
void EXC_systick(void) __attribute__((alias("EXC_blinky")));
static void EXC_blinky(void)
{
    uint8_t exc = (uint8_t)read_special(psr);
    /* Extinguish the LED(s) permanently. */
    IRQ_global_disable();
    printk("**FAILED** [Exception #%u]\n", exc);
    gpio_write_pin(gpiob, 12, HIGH);
    gpio_write_pin(gpioc, 13, HIGH);
    for (;;);
}

static void report(bool_t ok)
{
    if (ok) {
        printk("OK\n");
    } else {
        /* Extinguish the LED(s) permanently. */
        IRQ_global_disable();
        printk("**FAILED**\n");
        gpio_write_pin(gpiob, 12, HIGH);
        gpio_write_pin(gpioc, 13, HIGH);
    }
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
    report((i2c->oar1 == 0x10) && (i2c->cr1 == (I2C_CR1_ACK | I2C_CR1_PE)));
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
    report(spi->cr2 == (SPI_CR2_TXDMAEN | SPI_CR2_RXDMAEN));
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
    report(tim->arr == (5000-1));
}

static void flash_test(void)
{
    uint32_t fp, *p;
    int i;

    /* Erase and write the last page of Flash. Check it reads back okay. */
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
    report(TRUE);
    return;
fail:
    report(FALSE);
}

int main(void)
{
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
#if NR_I2C >= 1
    rcc->apb1enr |= RCC_APB1ENR_I2C1EN;
    i2c_test(i2c1, 1);
#endif
#if NR_I2C >= 2
    rcc->apb1enr |= RCC_APB1ENR_I2C2EN;
    i2c_test(i2c2, 2);
#endif

    /* Test SPI peripherals. */
#if NR_SPI >= 1
    rcc->apb2enr |= RCC_APB2ENR_SPI1EN;
    spi_test(spi1, 1);
#endif
#if NR_SPI >= 2
    rcc->apb1enr |= RCC_APB1ENR_SPI2EN;
    spi_test(spi2, 2);
#endif

    /* Test TIM peripherals, set up to overflow at 2Hz. */
#if NR_TIM >= 1
    tim_test(tim1, 1);
#endif
#if NR_TIM >= 2
    tim_test(tim2, 2);
#endif
#if NR_TIM >= 3
    tim_test(tim3, 3);
#endif
#if NR_TIM >= 4
    tim_test(tim4, 4);
#endif

    /* Test Flash. */
    flash_test();

    /* Enable TIM4 IRQ, to be triggered at 2Hz. */
    printk("Enable TIM4 IRQ... ");
    IRQx_set_prio(IRQ_TIM4, TIMER_IRQ_PRI);
    IRQx_clear_pending(IRQ_TIM4);
    IRQx_enable(IRQ_TIM4);
    report(TRUE);

    /* Endlessly test SRAM by filling with pseudorandom junk and then 
     * testing the values read back okay. */
    printk("Testing %ukB SRAM (endless loop)...", SRAM_KB);
    for (;;) {
        uint32_t *p = (uint32_t *)_ebss, sr = srand;
        while (p < (uint32_t *)(0x20000000 + SRAM_KB*1024))
            *p++ = rand();
        srand = sr;
        p = (uint32_t *)_ebss;
        while (p < (uint32_t *)(0x20000000 + SRAM_KB*1024)) {
            if (*p++ != rand()) {
                report(FALSE);
                for (;;);
            }
        }
    }

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
