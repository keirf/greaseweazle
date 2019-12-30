/*
 * floppy_f7.c
 * 
 * Floppy interface control: STM32F730x8.
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

#define O_FALSE 1
#define O_TRUE  0

#define GPO_bus GPO_opendrain(IOSPD_LOW,O_FALSE)
#define AFO_bus AFO_opendrain(IOSPD_LOW)
#define GPI_bus GPI_floating

/* Input pins */
#define gpio_index  gpiob
#define pin_index   2 /* PB2 */
#define gpio_trk0   gpioa
#define pin_trk0    3 /* PA3 */
#define gpio_wrprot gpioa
#define pin_wrprot  1 /* PA1 */

/* Output pins. */
#define gpio_densel gpiob
#define pin_densel 12 /* PB12 */
#define gpio_sel0  gpiob
#define pin_sel0   11 /* PB11 */
#define gpio_mot0  gpiob
#define pin_mot0   1  /* PB1 */
#define gpio_sel1  gpiob
#define pin_sel1   0  /* PB0 */
#define gpio_mot1  gpiob
#define pin_mot1   10 /* PB10 */
#define gpio_dir   gpioc
#define pin_dir    4  /* PC4 */
#define gpio_step  gpioa
#define pin_step   7  /* PA7 */
#define gpio_wgate gpioa
#define pin_wgate  6  /* PA6 */
#define gpio_side  gpioc
#define pin_side   3  /* PC3 */

/* RDATA: Pin A0, Timer 2 Channel 1, DMA1 Stream 5 Channel 3. */
#define gpio_rdata  gpioa
#define pin_rdata   0
#define tim_rdata   (tim2)
#define dma_rdata   (dma1->str[5])

/* WDATA: Pin A2, Timer 2 Channel 3, DMA1 Stream 1 Channel 3. */
#define gpio_wdata  gpioa
#define pin_wdata   2
#define tim_wdata   (tim2)
#define dma_wdata   (dma1->str[1])

typedef uint32_t timcnt_t;
#define TIM_PSC (SYSCLK_MHZ/72)

#define irq_index 8
void IRQ_8(void) __attribute__((alias("IRQ_INDEX_changed"))); /* EXTI2 */

#define irq_index_delay 31
void IRQ_31(void) __attribute__((alias("IRQ_INDEX_delay")));

static void floppy_mcu_init(void)
{
    /* Enable clock for Timer 2. */
    rcc->apb1enr |= RCC_APB1ENR_TIM2EN;
    peripheral_clock_delay();

    /* Set RDATA/WDATA as Timer pins. */
    gpio_set_af(gpio_rdata, pin_rdata, 1);
    gpio_set_af(gpio_wdata, pin_wdata, 1);
    configure_pin(rdata, AFI(PUPD_none));

    /* Set up EXTI mapping for INDEX: PB[3:0] -> EXT[3:0] */
    syscfg->exticr1 = 0x1111;
}

static void rdata_prep(void)
{
    /* RDATA Timer setup: 
     * The counter runs from 0x00000000-0xFFFFFFFF inclusive.
     * The prescaler is used to reduce the clock rate to 72MHz.
     *  
     * Ch.1 (RDATA) is in Input Capture mode, sampling on every clock and with
     * no input prescaling or filtering. Samples are captured on the falling 
     * edge of the input (CCxP=1). DMA is used to copy the sample into a ring
     * buffer for batch processing in the DMA-completion ISR. */
    tim_rdata->psc = TIM_PSC-1;
    tim_rdata->arr = 0xffffffff;
    tim_rdata->ccmr1 = TIM_CCMR1_CC1S(TIM_CCS_INPUT_TI1);
    tim_rdata->dier = TIM_DIER_CC1DE;
    tim_rdata->cr2 = 0;
    tim_rdata->egr = TIM_EGR_UG; /* update CNT, PSC, ARR */
    tim_rdata->sr = 0; /* dummy write */

    /* RDATA DMA setup: From the RDATA Timer's CCRx into a circular buffer. */
    dma_rdata.par = (uint32_t)(unsigned long)&tim_rdata->ccr1;
    dma_rdata.cr = (DMA_CR_CHSEL(3) |
                    DMA_CR_PL_HIGH |
                    DMA_CR_MSIZE_32BIT |
                    DMA_CR_PSIZE_32BIT |
                    DMA_CR_MINC |
                    DMA_CR_CIRC |
                    DMA_CR_DIR_P2M);
    dma_rdata.cr |= DMA_CR_EN;

    tim_rdata->ccer = TIM_CCER_CC1E | TIM_CCER_CC1P;
}

static void wdata_prep(void)
{
    /* WDATA Timer setup:
     * The counter is incremented at 72MHz.
     *  
     * Ch.3 (WDATA) is in PWM mode 1. It outputs O_TRUE for 400ns and then 
     * O_FALSE until the counter reloads. By changing the ARR via DMA we alter
     * the time between (fixed-width) O_TRUE pulses, mimicking floppy drive 
     * timings. */
    tim_wdata->psc = TIM_PSC-1;
    tim_wdata->ccmr2 = (TIM_CCMR2_CC3S(TIM_CCS_OUTPUT) |
                        TIM_CCMR2_OC3M(TIM_OCM_PWM1));
    tim_wdata->ccer = TIM_CCER_CC3E | ((O_TRUE==0) ? TIM_CCER_CC3P : 0);
    tim_wdata->ccr3 = sysclk_ns(400) / TIM_PSC;
    tim_wdata->dier = TIM_DIER_UDE;
    tim_wdata->cr2 = 0;
}

static void dma_wdata_start(void)
{
    dma_wdata.cr = (DMA_CR_CHSEL(3) |
                    DMA_CR_PL_HIGH |
                    DMA_CR_MSIZE_32BIT |
                    DMA_CR_PSIZE_32BIT |
                    DMA_CR_MINC |
                    DMA_CR_CIRC |
                    DMA_CR_DIR_M2P);
    dma_wdata.cr |= DMA_CR_EN;
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
