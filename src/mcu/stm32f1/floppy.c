/*
 * f1/floppy.c
 * 
 * Floppy interface control: STM32F103C8.
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

#define O_FALSE 1
#define O_TRUE  0

#define GPO_bus_pp GPO_pushpull(_2MHz,O_FALSE)
#define AFO_bus_pp AFO_pushpull(_2MHz)
#define GPO_bus_od GPO_opendrain(_2MHz,O_FALSE)
#define AFO_bus_od AFO_opendrain(_2MHz)
static unsigned int GPO_bus;
static unsigned int AFO_bus;
static unsigned int GPI_bus;

/* Input pins */
#define gpio_index  gpiob
#define pin_index   6 /* PB6 */
#define gpio_trk0   gpiob
#define pin_trk0    7 /* PB7 */
#define gpio_wrprot gpiob
#define pin_wrprot  8 /* PB8 */

/* Output pins. */
#define gpio_dir   gpiob
#define pin_dir    12 /* PB12 */
#define gpio_step  gpiob
#define pin_step   13 /* PB13 */
#define gpio_wgate gpiob
#define pin_wgate  14 /* PB14 */
#define gpio_head  gpiob
#define pin_head   15 /* PB15 */

/* RDATA: Pin B3, Timer 2 Channel 2, DMA1 Channel 7. */
#define gpio_rdata  gpiob
#define pin_rdata   3
#define tim_rdata   (tim2)
#define dma_rdata   (dma1->ch7)

/* WDATA: Pin B4, Timer 3 Channel 1, DMA1 Channel 3. */
#define gpio_wdata  gpiob
#define pin_wdata   4
#define tim_wdata   (tim3)
#define dma_wdata   (dma1->ch3)

typedef uint16_t timcnt_t;

#define irq_index 23
void IRQ_23(void) __attribute__((alias("IRQ_INDEX_changed"))); /* EXTI9_5 */

static unsigned int U_BUF_SZ;

static void floppy_mcu_init(void)
{
    const struct pin_mapping *mpin;
    const struct pin_mapping *upin;
    unsigned int avail_kb;

    avail_kb = sram_kb - ((((unsigned long)_ebss - 0x20000000) + 1023) >> 10);
    for (U_BUF_SZ = 128; U_BUF_SZ > avail_kb; U_BUF_SZ >>= 1)
        continue;
    U_BUF_SZ <<= 10;

    switch (gw_info.hw_submodel) {
    case F1SM_basic:
        /* Determine whether input pins must be internally pulled down. */
        configure_pin(index, GPI_pull_down);
        delay_us(10);
        GPI_bus = (get_index() == LOW) ? GPI_pull_up : GPI_floating;
        break;
    case F1SM_plus:
    case F1SM_plus_unbuffered:
        GPI_bus = GPI_floating;
        break;
    }

    printk("Floppy Inputs: %sternal Pullup\n",
           (GPI_bus == GPI_pull_up) ? "In" : "Ex");

    /* Remap timers to RDATA/WDATA pins. */
    afio->mapr |= (AFIO_MAPR_TIM2_REMAP_PARTIAL_1
                   | AFIO_MAPR_TIM3_REMAP_PARTIAL);

    configure_pin(rdata, GPI_bus);

    /* Configure user-modifiable pins. */
    for (upin = board_config->user_pins; upin->pin_id != 0; upin++) {
        gpio_configure_pin(gpio_from_id(upin->gpio_bank), upin->gpio_pin,
                           upin->push_pull ? GPO_bus_pp : GPO_bus_od);
    }

    /* Configure the standard output types. */
    GPO_bus = upin->push_pull ? GPO_bus_pp : GPO_bus_od;
    AFO_bus = upin->push_pull ? AFO_bus_pp : AFO_bus_od;

    /* Configure SELECT/MOTOR lines. */
    for (mpin = board_config->msel_pins; mpin->pin_id != 0; mpin++) {
        gpio_configure_pin(gpio_from_id(mpin->gpio_bank), mpin->gpio_pin,
                           GPO_bus);
    }

    /* Set up EXTI mapping for INDEX: PB[15:0] -> EXT[15:0] */
    afio->exticr1 = afio->exticr2 = afio->exticr3 = afio->exticr4 = 0x1111;
}

static void rdata_prep(void)
{
    /* RDATA Timer setup: 
     * The counter runs from 0x0000-0xFFFF inclusive at SAMPLE rate.
     *  
     * Ch.2 (RDATA) is in Input Capture mode, sampling on every clock and with
     * no input prescaling or filtering. Samples are captured on the falling 
     * edge of the input (CCxP=1). DMA is used to copy the sample into a ring
     * buffer for batch processing in the DMA-completion ISR. */
    tim_rdata->psc = TIM_PSC-1;
    tim_rdata->arr = 0xffff;
    tim_rdata->ccmr1 = TIM_CCMR1_CC2S(TIM_CCS_INPUT_TI1);
    tim_rdata->dier = TIM_DIER_CC2DE;
    tim_rdata->cr2 = 0;
    tim_rdata->egr = TIM_EGR_UG; /* update CNT, PSC, ARR */
    tim_rdata->sr = 0; /* dummy write */

    /* RDATA DMA setup: From the RDATA Timer's CCRx into a circular buffer. */
    dma_rdata.par = (uint32_t)(unsigned long)&tim_rdata->ccr2;
    dma_rdata.cr = (DMA_CR_PL_HIGH |
                    DMA_CR_MSIZE_16BIT |
                    DMA_CR_PSIZE_16BIT |
                    DMA_CR_MINC |
                    DMA_CR_CIRC |
                    DMA_CR_DIR_P2M |
                    DMA_CR_EN);

    tim_rdata->ccer = TIM_CCER_CC2E | TIM_CCER_CC2P;
}

static void wdata_prep(void)
{
    /* WDATA Timer setup:
     * The counter is incremented at SAMPLE rate. 
     *  
     * Ch.1 (WDATA) is in PWM mode 1. It outputs O_TRUE for 400ns and then 
     * O_FALSE until the counter reloads. By changing the ARR via DMA we alter
     * the time between (fixed-width) O_TRUE pulses, mimicking floppy drive 
     * timings. */
    tim_wdata->psc = TIM_PSC-1;
    tim_wdata->ccmr1 = (TIM_CCMR1_CC1S(TIM_CCS_OUTPUT) |
                        TIM_CCMR1_OC1M(TIM_OCM_PWM1));
    tim_wdata->ccer = TIM_CCER_CC1E | ((O_TRUE==0) ? TIM_CCER_CC1P : 0);
    tim_wdata->ccr1 = sample_ns(400);
    tim_wdata->dier = TIM_DIER_UDE;
    tim_wdata->cr2 = 0;
}

static void dma_wdata_start(void)
{
    dma_wdata.cr = (DMA_CR_PL_HIGH |
                    DMA_CR_MSIZE_16BIT |
                    DMA_CR_PSIZE_16BIT |
                    DMA_CR_MINC |
                    DMA_CR_CIRC |
                    DMA_CR_DIR_M2P |
                    DMA_CR_EN);
}

static uint8_t mcu_get_floppy_pin(unsigned int pin, uint8_t *p_level)
{
    switch (gw_info.hw_submodel) {
    case F1SM_plus:
    case F1SM_plus_unbuffered:
        if (pin == 34) {
            *p_level = gpio_read_pin(gpioa, 8);
            return ACK_OKAY;
        }
        break;
    }
    return ACK_BAD_PIN;
}

static void flippy_trk0_sensor(bool_t level)
{
    if (board_config->flippy) {
        gpio_write_pin(gpioa, 2, level);
        delay_us(10);
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
