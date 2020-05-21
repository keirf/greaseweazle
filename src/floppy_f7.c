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

#define GPO_bus_pp GPO_pushpull(IOSPD_LOW,O_FALSE)
#define AFO_bus_pp AFO_pushpull(IOSPD_LOW)
#define GPO_bus_od GPO_opendrain(IOSPD_LOW,O_FALSE)
#define AFO_bus_od AFO_opendrain(IOSPD_LOW)
static unsigned int GPO_bus;
static unsigned int AFO_bus;
#define GPI_bus GPI_floating

/* Input pins */
#define gpio_index  gpiob
#define pin_index   2 /* PB2 */
#define gpio_trk0   gpioa
#define pin_trk0    3 /* PA3 */
#define gpio_wrprot gpioa
#define pin_wrprot  1 /* PA1 */

/* Output pins. */
#define gpio_pin10 gpiob
#define pin_pin10  1  /* PB1 */
#define gpio_pin12 gpiob
#define pin_pin12  0  /* PB0 */
#define gpio_pin14 gpiob
#define pin_pin14  11 /* PB11 */
#define gpio_pin16 gpiob
#define pin_pin16  10 /* PB10 */
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

#define irq_index 8
void IRQ_8(void) __attribute__((alias("IRQ_INDEX_changed"))); /* EXTI2 */

/* We sometimes cast u_buf to uint32_t[], hence the alignment constraint. */
#define U_BUF_SZ (128*1024)
static uint8_t u_buf[U_BUF_SZ] aligned(4) section_ext_ram;

enum { _A = 1, _B, _C, _D, _E, _F, _G, _H, _I };
enum { _OD = 0, _PP };
struct user_pin {
    uint8_t pin_id;
    uint8_t gpio_bank;
    uint8_t gpio_pin;
    bool_t  push_pull;
};

const static struct user_pin _user_pins_F7SM_basic[] = {
    { 2, _B, 12, _OD },
    { 0,  0,  0, _OD } };
const static struct user_pin _user_pins_F7SM_ambertronic_f7_plus[] = {
    { 2, _B, 12, _OD }, /* board bug: B12 isn't buffered */
    { 4, _C,  6, _PP },
    { 0,  0,  0, _PP } };
const static struct user_pin _user_pins_F7SM_ultra730[] = {
    { 2, _B, 12, _PP },
    { 4, _E, 15, _PP },
    { 6, _E, 14, _PP },
    { 0,  0,  0, _PP } };
const static struct user_pin *user_pins, *_user_pins[] = {
    [F7SM_basic]               = _user_pins_F7SM_basic,
    [F7SM_ambertronic_f7_plus] = _user_pins_F7SM_ambertronic_f7_plus,
    [F7SM_ultra730]            = _user_pins_F7SM_ultra730
};

static GPIO gpio_from_id(uint8_t id)
{
    switch (id) {
    case _A: return gpioa;
    case _B: return gpiob;
    case _C: return gpioc;
    case _D: return gpiod;
    case _E: return gpioe;
    case _F: return gpiof;
    case _G: return gpiog;
    case _H: return gpioh;
    case _I: return gpioi;
    }
    ASSERT(0);
    return NULL;
}

static void floppy_mcu_init(void)
{
    const struct user_pin *upin;

    /* Enable clock for Timer 2. */
    rcc->apb1enr |= RCC_APB1ENR_TIM2EN;
    peripheral_clock_delay();

    /* Set RDATA/WDATA as Timer pins. */
    gpio_set_af(gpio_rdata, pin_rdata, 1);
    gpio_set_af(gpio_wdata, pin_wdata, 1);
    configure_pin(rdata, AFI(PUPD_none));

    /* Configure user-modifiable pins. */
    user_pins = _user_pins[gw_info.hw_submodel];
    for (upin = user_pins; upin->gpio_bank != 0; upin++) {
        gpio_configure_pin(gpio_from_id(upin->gpio_bank), upin->gpio_pin,
                           upin->push_pull ? GPO_bus_pp : GPO_bus_od);
    }

    /* Configure the standard output types. */
    GPO_bus = upin->push_pull ? GPO_bus_pp : GPO_bus_od;
    AFO_bus = upin->push_pull ? AFO_bus_pp : AFO_bus_od;

    /* Configure SELECT/MOTOR lines. */
    configure_pin(pin10, GPO_bus);
    configure_pin(pin12, GPO_bus);
    configure_pin(pin14, GPO_bus);
    configure_pin(pin16, GPO_bus);

    /* Set up EXTI mapping for INDEX: PB[3:0] -> EXT[3:0] */
    syscfg->exticr1 = 0x1111;
}

static void rdata_prep(void)
{
    /* RDATA Timer setup: 
     * The counter runs from 0x00000000-0xFFFFFFFF inclusive at SAMPLE rate.
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
     * The counter is incremented at SAMPLE rate.
     *  
     * Ch.3 (WDATA) is in PWM mode 1. It outputs O_TRUE for 400ns and then 
     * O_FALSE until the counter reloads. By changing the ARR via DMA we alter
     * the time between (fixed-width) O_TRUE pulses, mimicking floppy drive 
     * timings. */
    tim_wdata->psc = TIM_PSC-1;
    tim_wdata->ccmr2 = (TIM_CCMR2_CC3S(TIM_CCS_OUTPUT) |
                        TIM_CCMR2_OC3M(TIM_OCM_PWM1));
    tim_wdata->ccer = TIM_CCER_CC3E | ((O_TRUE==0) ? TIM_CCER_CC3P : 0);
    tim_wdata->ccr3 = sample_ns(400);
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

static void drive_deselect(void)
{
    if (unit_nr == -1)
        return;

    switch (bus_type) {
    case BUS_IBMPC:
        switch (unit_nr) {
        case 0: write_pin(pin14, FALSE); break;
        case 1: write_pin(pin12, FALSE); break;
        }
        break;
    case BUS_SHUGART:
        switch (unit_nr) {
        case 0: write_pin(pin10, FALSE); break;
        case 1: write_pin(pin12, FALSE); break;
        case 2: write_pin(pin14, FALSE); break;
        }
        break;
    }

    unit_nr = -1;
}

static uint8_t drive_select(uint8_t nr)
{
    if (nr == unit_nr)
        return ACK_OKAY;

    drive_deselect();

    switch (bus_type) {
    case BUS_IBMPC:
        switch (nr) {
        case 0: write_pin(pin14, TRUE); break;
        case 1: write_pin(pin12, TRUE); break;
        default: return ACK_BAD_UNIT;
        }
        break;
    case BUS_SHUGART:
        switch (nr) {
        case 0: write_pin(pin10, TRUE); break;
        case 1: write_pin(pin12, TRUE); break;
        case 2: write_pin(pin14, TRUE); break;
        default: return ACK_BAD_UNIT;
        }
        break;
    default:
        return ACK_NO_BUS;
    }

    unit_nr = nr;
    delay_us(delay_params.select_delay);

    return ACK_OKAY;
}

static uint8_t drive_motor(uint8_t nr, bool_t on)
{
    switch (bus_type) {
    case BUS_IBMPC:
        if (nr >= 2) 
            return ACK_BAD_UNIT;
        if (unit[nr].motor == on)
            return ACK_OKAY;
        switch (nr) {
        case 0: write_pin(pin10, on); break;
        case 1: write_pin(pin16, on); break;
        }
        break;
    case BUS_SHUGART:
        if (nr >= 3)
            return ACK_BAD_UNIT;
        /* All shugart units share one motor line. Alias them all to unit 0. */
        nr = 0;
        if (unit[nr].motor == on)
            return ACK_OKAY;
        write_pin(pin16, on);
        break;
    default:
        return ACK_NO_BUS;
    }

    unit[nr].motor = on;
    if (on)
        delay_ms(delay_params.motor_delay);

    return ACK_OKAY;

}

static void reset_bus(void)
{
    write_pin(pin10, FALSE);
    write_pin(pin12, FALSE);
    write_pin(pin14, FALSE);
    write_pin(pin16, FALSE);
}

static uint8_t set_user_pin(unsigned int pin, unsigned int level)
{
    const struct user_pin *upin;

    for (upin = user_pins; upin->gpio_bank != 0; upin++) {
        if (upin->pin_id == pin)
            goto found;
    }
    return ACK_BAD_PIN;

found:
    gpio_write_pin(gpio_from_id(upin->gpio_bank), upin->gpio_pin, level);
    return ACK_OKAY;
}

static void reset_user_pins(void)
{
    const struct user_pin *upin;

    for (upin = user_pins; upin->gpio_bank != 0; upin++)
        gpio_write_pin(gpio_from_id(upin->gpio_bank), upin->gpio_pin, O_FALSE);
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
