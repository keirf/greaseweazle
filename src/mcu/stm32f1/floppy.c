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

#define GPO_bus GPO_opendrain(_2MHz,O_FALSE)
#define AFO_bus AFO_opendrain(_2MHz)
static unsigned int GPI_bus;

/* Input pins */
#define gpio_index  gpiob
#define pin_index   6 /* PB6 */
#define gpio_trk0   gpiob
#define pin_trk0    7 /* PB7 */
#define gpio_wrprot gpiob
#define pin_wrprot  8 /* PB8 */

/* Output pins. */
#define gpio_densel gpiob
#define pin_densel  9 /* PB9 */
#define gpio_sel   gpiob
#define pin_sel    10 /* PB10 */
#define gpio_mot   gpiob
#define pin_mot    11 /* PB11 */
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

/* We sometimes cast u_buf to uint32_t[], hence the alignment constraint. */
#define U_BUF_SZ 8192
static uint8_t u_buf[U_BUF_SZ] aligned(4);

static void floppy_mcu_init(void)
{
    /* Determine whether input pins must be internally pulled down. */
    configure_pin(index, GPI_pull_down);
    delay_us(10);
    GPI_bus = (get_index() == LOW) ? GPI_pull_up : GPI_floating;
    printk("Floppy Inputs: %sternal Pullup\n",
           (GPI_bus == GPI_pull_up) ? "In" : "Ex");

    /* Remap timers to RDATA/WDATA pins. */
    afio->mapr |= (AFIO_MAPR_TIM2_REMAP_PARTIAL_1
                   | AFIO_MAPR_TIM3_REMAP_PARTIAL);

    /* Set up EXTI mapping for INDEX: PB[15:0] -> EXT[15:0] */
    afio->exticr1 = afio->exticr2 = afio->exticr3 = afio->exticr4 = 0x1111;

    configure_pin(rdata, GPI_bus);

    /* Configure SELECT/MOTOR lines. */
    configure_pin(sel, GPO_bus);
    configure_pin(mot, GPO_bus);

    /* Configure user-modifiable lines. */
    configure_pin(densel, GPO_bus);
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

static void drive_deselect(void)
{
    write_pin(sel, FALSE);
    unit_nr = -1;
}

static uint8_t drive_select(uint8_t nr)
{
    write_pin(sel, TRUE);
    unit_nr = 0;
    delay_us(delay_params.select_delay);
    return ACK_OKAY;
}

static uint8_t drive_motor(uint8_t nr, bool_t on)
{
    if (unit[0].motor == on)
        return ACK_OKAY;

    write_pin(mot, on);
    unit[0].motor = on;
    if (on)
        delay_ms(delay_params.motor_delay);

    return ACK_OKAY;
}

static uint8_t mcu_get_floppy_pin(unsigned int pin, uint8_t *p_level)
{
    return ACK_BAD_PIN;
}

static uint8_t set_user_pin(unsigned int pin, unsigned int level)
{
    if (pin != 2)
        return ACK_BAD_PIN;
    gpio_write_pin(gpio_densel, pin_densel, level);
    return ACK_OKAY;
}

static void reset_user_pins(void)
{
    write_pin(densel, FALSE);
}

/* No Flippy-modded drive support on F1 boards. */
#define flippy_trk0_sensor_disable() ((void)0)
#define flippy_trk0_sensor_enable() ((void)0)
#define flippy_detect() FALSE

/*
 * Local variables:
 * mode: C
 * c-file-style: "Linux"
 * c-basic-offset: 4
 * tab-width: 4
 * indent-tabs-mode: nil
 * End:
 */
