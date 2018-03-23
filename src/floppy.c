/*
 * floppy.c
 * 
 * Floppy interface control.
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

#define O_FALSE 1
#define O_TRUE  0

#define GPO_bus GPO_opendrain(_2MHz,O_FALSE)
#define AFO_bus (AFO_opendrain(_2MHz) | (O_FALSE<<4))

#define m(bitnr) (1u<<(bitnr))

#define gpio_floppy gpiob

/* Input pins */
#define pin_index   6 /* PB6 */
#define pin_trk0    7 /* PB7 */
#define pin_wrprot  8 /* PB8 */
#define get_index()   gpio_read_pin(gpio_floppy, pin_index)
#define get_trk0()    gpio_read_pin(gpio_floppy, pin_trk0)
#define get_wrprot()  gpio_read_pin(gpio_floppy, pin_wrprot)

/* Output pins. */
#define pin_densel  9 /* PB9 */
#define pin_sel0   10 /* PB10 */
#define pin_motor  11 /* PB11 */
#define pin_dir    12 /* PB12 */
#define pin_step   13 /* PB13 */
#define pin_wgate  14 /* PB14 */
#define pin_side   15 /* PB15 */

/* Track and modify states of output pins. */
static struct {
    bool_t densel;
    bool_t sel0;
    bool_t motor;
    bool_t dir;
    bool_t step;
    bool_t wgate;
    bool_t side;
} pins;
#define read_pin(pin) pins.pin
#define write_pin(pin, level) ({                                        \
    gpio_write_pin(gpio_floppy, pin_##pin, level ? O_TRUE : O_FALSE);   \
    pins.pin = level; })

#define gpio_data gpiob

#define pin_rdata   3
#define tim_rdata   (tim2)
#define dma_rdata   (dma1->ch7)

#define pin_wdata   4
#define tim_wdata   (tim3)
#define dma_wdata   (dma1->ch3)

#define irq_index 23
void IRQ_23(void) __attribute__((alias("IRQ_INDEX_changed"))); /* EXTI9_5 */
static volatile struct index {
    unsigned int count;
    time_t timestamp;
    time_t duration;
    unsigned int read_prod;
} index;

/* A DMA buffer for running a timer associated with a floppy-data I/O pin. */
static struct dma_ring {
    /* Indexes into the buf[] ring buffer. */
    uint16_t cons; /* dma_rd: our consumer index for flux samples */
    union {
        uint16_t prod; /* dma_wr: our producer index for flux samples */
        uint16_t prev_sample; /* dma_rd: previous CCRx sample value */
    };
    /* DMA ring buffer of timer values (ARR or CCRx). */
    uint16_t buf[512];
} dma;

static enum {
    ST_inactive,
    ST_command_wait,
    ST_read_flux_wait_index,
    ST_read_flux,
    ST_read_flux_drain,
    ST_write_flux_wait_data,
    ST_write_flux_wait_index,
    ST_write_flux,
    ST_write_flux_drain,
} floppy_state = ST_inactive;

#define FLOPPY_EP 2
#define FLOPPY_MPS 64

static uint8_t u_buf[8192];
static uint32_t u_cons, u_prod;
#define U_MASK(x) ((x)&(sizeof(u_buf)-1))

static struct delay_params {
    uint16_t step_delay;
    uint16_t seek_settle;
    uint16_t motor_delay;
    uint16_t auto_off;
} delay_params = {
    .step_delay = 3,
    .seek_settle = 15,
    .motor_delay = 750,
    .auto_off = 3000
};

static void step_one_out(void)
{
    write_pin(dir, FALSE);
    delay_us(10);
    write_pin(step, TRUE);
    delay_us(10);
    write_pin(step, FALSE);
    delay_ms(delay_params.step_delay);
}

static void step_one_in(void)
{
    write_pin(dir, TRUE);
    delay_us(10);
    write_pin(step, TRUE);
    delay_us(10);
    write_pin(step, FALSE);
    delay_ms(delay_params.step_delay);
}

static int cur_cyl = -1;

static void drive_select(void)
{
    write_pin(sel0, TRUE);
    delay_us(10);
}

static void drive_deselect(void)
{
    delay_us(10);
    write_pin(sel0, FALSE);
}

static bool_t floppy_seek(unsigned int cyl)
{
    drive_select();

    if ((cyl == 0) || (cur_cyl < 0)) {

        unsigned int i;
        for (i = 0; i < 256; i++) {
            if (get_trk0() == LOW)
                break;
            step_one_out();
        }
        cur_cyl = 0;
        if (get_trk0() == HIGH) {
            drive_deselect();
            cur_cyl = -1;
            return FALSE;
        }

    }

    if (cur_cyl < 0) {

    } else if (cur_cyl <= cyl) {

        unsigned int nr = cyl - cur_cyl;
        while (nr--)
            step_one_in();

    } else {

        unsigned int nr = cur_cyl - cyl;
        while (nr--)
            step_one_out();

    }

    drive_deselect();

    delay_ms(delay_params.seek_settle);
    cur_cyl = cyl;

    return TRUE;
}

static void floppy_motor(bool_t on)
{
    if (read_pin(motor) == on)
        return;
    write_pin(motor, on);
    if (on)
        delay_ms(delay_params.motor_delay);
}

static void floppy_flux_end(void)
{
    /* Turn off timers. */
    tim_rdata->ccer = 0;
    tim_rdata->cr1 = 0;
    tim_rdata->sr = 0; /* dummy, drains any pending DMA */
    tim_wdata->cr1 = 0;
    tim_wdata->sr = 0; /* dummy, drains any pending DMA */

    /* Turn off DMA. */
    dma_rdata.ccr = 0;
    dma_wdata.ccr = 0;

    /* Turn off write pins. */
    write_pin(wgate, FALSE);
    gpio_configure_pin(gpio_data, pin_wdata, GPO_bus);    
}

void floppy_reset(void)
{
    unsigned int i;

    floppy_state = ST_inactive;

    floppy_flux_end();

    /* Turn off all output pins. */
    for (i = 9; i <= 15; i++)
        gpio_write_pin(gpio_floppy, i, O_FALSE);
    memset(&pins, 0, sizeof(pins));
}

void floppy_init(void)
{
    unsigned int i, GPI_bus;

    /* Output pins, unbuffered. */
    for (i = 9; i <= 15; i++)
        gpio_configure_pin(gpio_floppy, i, GPO_bus);

    gpio_configure_pin(gpio_floppy, pin_index, GPI_pull_down);
    delay_us(10);
    GPI_bus = (get_index() == LOW) ? GPI_pull_up : GPI_floating;
    printk("Floppy Inputs: %sternal Pullup\n",
           (GPI_bus == GPI_pull_up) ? "In" : "Ex");

    /* Input pins. */
    for (i = 6; i <= 8; i++)
        gpio_configure_pin(gpio_floppy, i, GPI_bus);

    /* RDATA/WDATA */
    gpio_configure_pin(gpio_data, pin_rdata, GPI_bus);
    gpio_configure_pin(gpio_data, pin_wdata, GPO_bus);
    afio->mapr |= (AFIO_MAPR_TIM2_REMAP_PARTIAL_1
                   | AFIO_MAPR_TIM3_REMAP_PARTIAL);

    /* PB[15:0] -> EXT[15:0] */
    afio->exticr1 = afio->exticr2 = afio->exticr3 = afio->exticr4 = 0x1111;

    /* Configure INDEX-changed IRQ. */
    exti->rtsr = 0;
    exti->imr = exti->ftsr = m(pin_index);
    IRQx_set_prio(irq_index, INDEX_IRQ_PRI);
    IRQx_enable(irq_index);

    /* RDATA Timer setup: 
     * The counter runs from 0x0000-0xFFFF inclusive at full SYSCLK rate.
     *  
     * Ch.2 (RDATA) is in Input Capture mode, sampling on every clock and with
     * no input prescaling or filtering. Samples are captured on the falling 
     * edge of the input (CCxP=1). DMA is used to copy the sample into a ring
     * buffer for batch processing in the DMA-completion ISR. */
    tim_rdata->psc = 0;
    tim_rdata->arr = 0xffff;
    tim_rdata->ccmr1 = TIM_CCMR1_CC2S(TIM_CCS_INPUT_TI1);
    tim_rdata->dier = TIM_DIER_CC2DE;
    tim_rdata->cr2 = 0;

    /* RDATA DMA setup: From the RDATA Timer's CCRx into a circular buffer. */
    dma_rdata.cpar = (uint32_t)(unsigned long)&tim_rdata->ccr2;
    dma_rdata.cmar = (uint32_t)(unsigned long)dma.buf;

    /* WDATA Timer setup:
     * The counter is incremented at full SYSCLK rate. 
     *  
     * Ch.1 (WDATA) is in PWM mode 1. It outputs O_TRUE for 400ns and then 
     * O_FALSE until the counter reloads. By changing the ARR via DMA we alter
     * the time between (fixed-width) O_TRUE pulses, mimicking floppy drive 
     * timings. */
    tim_wdata->psc = 0;
    tim_wdata->ccmr1 = (TIM_CCMR1_CC1S(TIM_CCS_OUTPUT) |
                        TIM_CCMR1_OC1M(TIM_OCM_PWM1));
    tim_wdata->ccer = TIM_CCER_CC1E | ((O_TRUE==0) ? TIM_CCER_CC1P : 0);
    tim_wdata->ccr1 = sysclk_ns(400);
    tim_wdata->dier = TIM_DIER_UDE;
    tim_wdata->cr2 = 0;

    /* WDATA DMA setup: From a circular buffer into the WDATA Timer's ARR. */
    dma_wdata.cpar = (uint32_t)(unsigned long)&tim_wdata->arr;
    dma_wdata.cmar = (uint32_t)(unsigned long)dma.buf;
}


/* CMD_GET_INFO, length=3, 0. Returns 32 bytes after ACK. */
#define CMD_GET_INFO        0
/* CMD_SEEK, length=3, cyl# */
#define CMD_SEEK            1
/* CMD_SIDE, length=3, side# (0=bottom) */
#define CMD_SIDE            2
/* CMD_SET_DELAYS, length=2+4*2, <delay_params> */
#define CMD_SET_DELAYS      3
/* CMD_GET_DELAYS, length=2. Returns 4*2 bytes after ACK. */
#define CMD_GET_DELAYS      4
/* CMD_MOTOR, length=3, motor_state */
#define CMD_MOTOR           5
/* CMD_READ_FLUX, length=3, #revs. Returns flux readings until EOStream. */
#define CMD_READ_FLUX       6
/* CMD_WRITE_FLUX, length=2. Host follows with flux readings until EOStream. */
#define CMD_WRITE_FLUX      7
/* CMD_GET_FLUX_STATUS, length=2. Last read/write status returned in ACK. */
#define CMD_GET_FLUX_STATUS 8
/* CMD_GET_READ_INFO, length=2. Returns 7*8 bytes after ACK. */
#define CMD_GET_READ_INFO   9

#define ACK_OKAY            0
#define ACK_BAD_COMMAND     1
#define ACK_NO_INDEX        2
#define ACK_NO_TRK0         3
#define ACK_FLUX_OVERFLOW   4
#define ACK_FLUX_UNDERFLOW  5
#define ACK_WRPROT          6

const static struct __packed gw_info {
    uint8_t fw_major;
    uint8_t fw_minor;
    uint8_t max_rev;
    uint8_t max_cmd;
    uint32_t sample_freq;
} gw_info = {
    .fw_major = 0, .fw_minor = 1,
    .max_rev = 7, .max_cmd = CMD_GET_READ_INFO,
    .sample_freq = SYSCLK_MHZ * 1000000u
};

/*
 * READ PATH
 */

static struct {
    time_t start;
    uint8_t status;
    uint8_t rev;
    uint8_t nr_revs;
    bool_t packet_ready;
    bool_t write_finished;
    unsigned int packet_len;
    unsigned int nr_samples;
    uint8_t packet[FLOPPY_MPS];
} rw;

static struct {
    uint32_t time;
    uint32_t samples;
} read_info[7];

static bool_t rdata_encode_flux(void)
{
    const uint16_t buf_mask = ARRAY_SIZE(dma.buf) - 1;
    uint16_t cons, prod, prev = dma.prev_sample, curr, next;
    unsigned int nr_samples;

    /* Find out where the DMA engine's producer index has got to. */
    prod = ARRAY_SIZE(dma.buf) - dma_rdata.cndtr;
    nr_samples = (prod - dma.cons) & buf_mask;

    if (rw.rev != index.count) {
        unsigned int final_samples = U_MASK(index.read_prod - dma.cons);
        read_info[rw.rev].time = sysclk_stk(index.duration);
        read_info[rw.rev].samples = rw.nr_samples + final_samples;
        rw.rev++;
        nr_samples -= final_samples;
        rw.nr_samples = 0;
    }

    rw.nr_samples += nr_samples;

    /* Process the flux timings into the raw bitcell buffer. */
    for (cons = dma.cons; cons != prod; cons = (cons+1) & buf_mask) {
        next = dma.buf[cons];
        curr = next - prev;

        if (curr == 0) {
            /* 0: Skip. */
        } else if (curr < 250) {
            /* 1-249: One byte. */
            u_buf[U_MASK(u_prod++)] = curr;
        } else {
            unsigned int high = curr / 250;
            if (high <= 5) {
                /* 250-1500: Two bytes. */
                u_buf[U_MASK(u_prod++)] = 249 + high;
                u_buf[U_MASK(u_prod++)] = 1 + (curr % 250);
            } else {
                /* 1501-(2^28-1): Five bytes */
                u_buf[U_MASK(u_prod++)] = 0xff;
                u_buf[U_MASK(u_prod++)] = 1 | (curr << 1);
                u_buf[U_MASK(u_prod++)] = 1 | (curr >> 6);
                u_buf[U_MASK(u_prod++)] = 1 | (curr >> 13);
                u_buf[U_MASK(u_prod++)] = 1 | (curr >> 20);
            }
        }

        prev = next;
    }

    /* Save our progress for next time. */
    dma.cons = cons;
    dma.prev_sample = prev;
    return FALSE;
}

static void floppy_read_prep(unsigned int revs)
{
    /* Start DMA. */
    dma_rdata.cndtr = ARRAY_SIZE(dma.buf);
    dma_rdata.ccr = (DMA_CCR_PL_HIGH |
                     DMA_CCR_MSIZE_16BIT |
                     DMA_CCR_PSIZE_16BIT |
                     DMA_CCR_MINC |
                     DMA_CCR_CIRC |
                     DMA_CCR_DIR_P2M |
                     DMA_CCR_EN);

    /* DMA soft state. */
    dma.cons = 0;
    dma.prev_sample = tim_rdata->cnt;

    drive_select();
    floppy_motor(TRUE);

    index.count = 0;
    floppy_state = ST_read_flux_wait_index;
    memset(&rw, 0, sizeof(rw));
    rw.nr_revs = revs;
    rw.start = time_now();
    rw.status = ACK_OKAY;
}

static void floppy_read_wait_index(void)
{
    if (index.count == 0) {
        if (time_since(rw.start) > time_ms(2000)) {
            /* Timeout */
            printk("NO INDEX\n");
            floppy_flux_end();
            rw.status = ACK_NO_INDEX;
            floppy_state = ST_read_flux_drain;
        }
        return;
    }

    /* Start timer. */
    tim_rdata->ccer = TIM_CCER_CC2E | TIM_CCER_CC2P;
    tim_rdata->cr1 = TIM_CR1_CEN;

    index.count = 0;
    floppy_state = ST_read_flux;
}

static void make_read_packet(unsigned int n)
{
    unsigned int c = U_MASK(u_cons);
    unsigned int l = ARRAY_SIZE(u_buf) - c;
    if (l < n) {
        memcpy(rw.packet, &u_buf[c], l);
        memcpy(&rw.packet[l], u_buf, n-l);
    } else {
        memcpy(rw.packet, &u_buf[c], n);
    }
    u_cons += n;
    rw.packet_ready = TRUE;
}

static void floppy_read(void)
{
    unsigned int avail = (uint32_t)(u_prod - u_cons);

    if (floppy_state == ST_read_flux) {

        if (index.count >= rw.nr_revs) {
            floppy_flux_end();
            floppy_state = ST_read_flux_drain;
        }

        rdata_encode_flux();
        avail = (uint32_t)(u_prod - u_cons);

    } else if ((avail < FLOPPY_MPS)
               && !rw.packet_ready
               && ep_tx_ready(FLOPPY_EP)) {

        memset(rw.packet, 0, FLOPPY_MPS);
        make_read_packet(avail);
        usb_write(FLOPPY_EP, rw.packet, avail+1);
        floppy_configured();
        drive_deselect();
        return; /* FINISHED */

    }

    if (avail > sizeof(u_buf)) {
        /* Overflow */
        printk("OVERFLOW %u %u %u %u\n", u_cons, u_prod,
               rw.packet_ready, ep_tx_ready(FLOPPY_EP));
        floppy_flux_end();
        rw.status = ACK_FLUX_OVERFLOW;
        floppy_state = ST_read_flux_drain;
        u_cons = u_prod = 0;
    }

    if (!rw.packet_ready && (avail >= FLOPPY_MPS))
        make_read_packet(FLOPPY_MPS);

    if (rw.packet_ready && ep_tx_ready(FLOPPY_EP)) {
        usb_write(FLOPPY_EP, rw.packet, FLOPPY_MPS);
        rw.packet_ready = FALSE;
    }
}


/*
 * WRITE PATH
 */

static unsigned int _wdata_decode_flux(uint16_t *tbuf, unsigned int nr)
{
    unsigned int todo = nr;

    if (todo == 0)
        return 0;

    while (u_cons != u_prod) {
        uint8_t x = u_buf[U_MASK(u_cons)];
        uint32_t val = x;
        if (x == 0) {
            /* 0: Terminate */
            u_cons++;
            rw.write_finished = TRUE;
            goto out;
        } else if (x < 250) {
            /* 1-249: One byte */
            u_cons++;
        } else if (x == 255) {
            /* 255: Five bytes */
            uint32_t val;
            if ((uint32_t)(u_prod - u_cons) < 5)
                goto out;
            u_cons++;
            val  = (u_buf[U_MASK(u_cons++)]       ) >>  1;
            val |= (u_buf[U_MASK(u_cons++)] & 0xfe) <<  6;
            val |= (u_buf[U_MASK(u_cons++)] & 0xfe) << 13;
            val |= (u_buf[U_MASK(u_cons++)] & 0xfe) << 20;
            val = val ?: 1; /* Force non-zero */
        } else {
            /* 250-254: Two bytes */
            if ((uint32_t)(u_prod - u_cons) < 2)
                goto out;
            u_cons++;
            val = (x - 249) * 250;
            val += u_buf[U_MASK(u_cons++)] - 1;
        }

        *tbuf++ = val - 1 ?: 1; /* Force non-zero */
        if (!--todo)
            goto out;
    }

out:
    return nr - todo;
}

static void wdata_decode_flux(void)
{
    const uint16_t buf_mask = ARRAY_SIZE(dma.buf) - 1;
    uint16_t nr_to_wrap, nr_to_cons, nr, dmacons;

    /* Find out where the DMA engine's consumer index has got to. */
    dmacons = ARRAY_SIZE(dma.buf) - dma_wdata.cndtr;

    /* Find largest contiguous stretch of ring buffer we can fill. */
    nr_to_wrap = ARRAY_SIZE(dma.buf) - dma.prod;
    nr_to_cons = (dmacons - dma.prod - 1) & buf_mask;
    nr = min(nr_to_wrap, nr_to_cons);

    /* Now attempt to fill the contiguous stretch with flux data calculated 
     * from buffered bitcell data. */
    dma.prod += _wdata_decode_flux(&dma.buf[dma.prod], nr);
    dma.prod &= buf_mask;
}

static void floppy_process_write_packet(void)
{
    int len = ep_rx_ready(FLOPPY_EP);

    if ((len >= 0) && !rw.packet_ready) {
        usb_read(FLOPPY_EP, rw.packet, len);
        rw.packet_ready = TRUE;
        rw.packet_len = len;
    }

    if (rw.packet_ready) {
        unsigned int avail = ARRAY_SIZE(u_buf) - (uint32_t)(u_prod - u_cons);
        unsigned int n = rw.packet_len;
        if (avail >= n) {
            unsigned int p = U_MASK(u_prod);
            unsigned int l = ARRAY_SIZE(u_buf) - p;
            if (l < n) {
                memcpy(&u_buf[p], rw.packet, l);
                memcpy(u_buf, &rw.packet[l], n-l);
            } else {
                memcpy(&u_buf[p], rw.packet, n);
            }
            u_prod += n;
            rw.packet_ready = FALSE;
        }
    }
}

static void floppy_write_prep(void)
{
    /* Initialise DMA ring indexes (consumer index is implicit). */
    dma_wdata.cndtr = ARRAY_SIZE(dma.buf);
    dma.prod = 0;

    drive_select();
    floppy_motor(TRUE);

    floppy_state = ST_write_flux_wait_data;
    memset(&rw, 0, sizeof(rw));
    rw.status = ACK_OKAY;

    if (get_wrprot() == LOW) {
        floppy_flux_end();
        rw.status = ACK_WRPROT;
        floppy_state = ST_write_flux_drain;
    }
}

static void floppy_write_wait_data(void)
{
    floppy_process_write_packet();
    wdata_decode_flux();

    /* Wait for DMA and input buffers to fill, or write stream to end. */
    if (((dma.prod != (ARRAY_SIZE(dma.buf)-1)) 
         || ((uint32_t)(u_prod - u_cons) < (ARRAY_SIZE(u_buf) - 512)))
        && !rw.write_finished)
        return;

    index.count = 0;
    floppy_state = ST_write_flux_wait_index;
    rw.start = time_now();

    /* Enable DMA only after flux values are generated. */
    dma_wdata.ccr = (DMA_CCR_PL_HIGH |
                     DMA_CCR_MSIZE_16BIT |
                     DMA_CCR_PSIZE_16BIT |
                     DMA_CCR_MINC |
                     DMA_CCR_CIRC |
                     DMA_CCR_DIR_M2P |
                     DMA_CCR_EN);
}

static void floppy_write_wait_index(void)
{
    if (index.count == 0) {
        if (time_since(rw.start) > time_ms(2000)) {
            /* Timeout */
            floppy_flux_end();
            rw.status = ACK_NO_INDEX;
            floppy_state = ST_write_flux_drain;
        }
        return;
    }

    /* Start timer. */
    tim_wdata->egr = TIM_EGR_UG;
    tim_wdata->sr = 0; /* dummy write, gives h/w time to process EGR.UG=1 */
    tim_wdata->cr1 = TIM_CR1_CEN;

    /* Enable output. */
    gpio_configure_pin(gpio_data, pin_wdata, AFO_bus);
    write_pin(wgate, TRUE);

    index.count = 0;
    floppy_state = ST_write_flux;
}

static void floppy_write_check_underflow(void)
{
    uint32_t avail = u_prod - u_cons;

    if (/* We've run the input buffer dry. */
        (avail == 0)
        /* The input buffer is nearly dry, and doesn't contain EOStream. */
        || ((avail < 16) && (u_buf[U_MASK(u_prod-1)] != 0))) {

        /* Underflow */
        printk("UNDERFLOW %u %u %u %u\n", u_cons, u_prod,
               rw.packet_ready, ep_rx_ready(FLOPPY_EP));
        floppy_flux_end();
        rw.status = ACK_FLUX_UNDERFLOW;
        floppy_state = ST_write_flux_drain;

    }
}

static void floppy_write(void)
{
    uint16_t dmacons, todo, prev_todo;

    floppy_process_write_packet();
    wdata_decode_flux();

    if (!rw.write_finished) {
        floppy_write_check_underflow();
        return;
    }

    /* Wait for DMA ring to drain. */
    todo = ~0;
    do {
        /* Early termination on index pulse? */
//        if (wr->terminate_at_index && (index.count != index_count))
//            goto out;
        /* Check progress of draining the DMA ring. */
        prev_todo = todo;
        dmacons = ARRAY_SIZE(dma.buf) - dma_wdata.cndtr;
        todo = (dma.prod - dmacons) & (ARRAY_SIZE(dma.buf) - 1);
    } while ((todo != 0) && (todo <= prev_todo));

    floppy_flux_end();
    floppy_state = ST_write_flux_drain;
}

static void floppy_write_drain(void)
{
    /* Drain the write stream. */
    if (!rw.write_finished) {
        floppy_process_write_packet();
        (void)_wdata_decode_flux(dma.buf, ARRAY_SIZE(dma.buf));
        return;
    }

    /* Wait for space to write ACK packet. */
    if (!ep_tx_ready(FLOPPY_EP))
        return;

    /* ACK with Status byte. */
    u_buf[0] = rw.status;
    usb_write(FLOPPY_EP, u_buf, 1);

    /* Reset for next command. */
    floppy_configured();
    drive_deselect();
}

static void process_command(void)
{
    uint8_t cmd = u_buf[0];
    uint8_t len = u_buf[1];
    uint8_t resp_sz = 2;

    switch (cmd) {
    case CMD_GET_INFO: {
        uint8_t idx = u_buf[2];
        if (len != 3) goto bad_command;
        if (idx != 0) goto bad_command;
        memset(&u_buf[2], 0, 32);
        memcpy(&u_buf[2], &gw_info, sizeof(gw_info));
        resp_sz += 32;
        break;
    }
    case CMD_SEEK: {
        uint8_t cyl = u_buf[2];
        if (len != 3) goto bad_command;
        if (cyl > 85) goto bad_command;
        u_buf[1] = floppy_seek(cyl) ? ACK_OKAY : ACK_NO_TRK0;
        goto out;
    }
    case CMD_SIDE: {
        uint8_t side = u_buf[2];
        if (len != 3) goto bad_command;
        if (side > 1) goto bad_command;
        write_pin(side, side);
        break;
    }
    case CMD_SET_DELAYS: {
        if (len != (2+sizeof(delay_params))) goto bad_command;
        memcpy(&delay_params, &u_buf[2], sizeof(delay_params));
        break;
    }
    case CMD_GET_DELAYS: {
        if (len != 2) goto bad_command;
        memcpy(&u_buf[2], &delay_params, sizeof(delay_params));
        resp_sz += sizeof(delay_params);
        break;
    }
    case CMD_MOTOR: {
        uint8_t state = u_buf[2];
        if (len != 3) goto bad_command;
        if (state > 1) goto bad_command;
        floppy_motor(state);
        break;
    }
    case CMD_READ_FLUX: {
        uint8_t revs = u_buf[2];
        if (len != 3) goto bad_command;
        if ((revs == 0) || (revs > 7)) goto bad_command;
        floppy_read_prep(revs);
        break;
    }
    case CMD_WRITE_FLUX: {
        if (len != 2) goto bad_command;
        floppy_write_prep();
        break;
    }
    case CMD_GET_FLUX_STATUS: {
        if (len != 2) goto bad_command;
        u_buf[1] = rw.status;
        goto out;
    }
    case CMD_GET_READ_INFO: {
        if (len != 2) goto bad_command;
        memcpy(&u_buf[2], &read_info, sizeof(read_info));
        resp_sz += sizeof(read_info);
        break;
    }
    default:
        goto bad_command;
    }

    u_buf[1] = ACK_OKAY;
out:
    usb_write(FLOPPY_EP, u_buf, resp_sz);
    return;

bad_command:
    u_buf[1] = ACK_BAD_COMMAND;
    goto out;
}

void floppy_configured(void)
{
    floppy_state = ST_command_wait;
    u_cons = u_prod = 0;
}

void floppy_process(void)
{
    int len;

    switch (floppy_state) {

    case ST_command_wait:

        len = ep_rx_ready(FLOPPY_EP);
        if ((len >= 0) && (len < (sizeof(u_buf)-u_prod))) {
            usb_read(FLOPPY_EP, &u_buf[u_prod], len);
            u_prod += len;
        }

        if ((u_prod >= 2) && (u_prod >= u_buf[1]) && ep_tx_ready(FLOPPY_EP)) {
            /* Process command and reset for next command. */
            process_command();
            u_cons = u_prod = 0;
        }

        break;

    case ST_read_flux_wait_index:
        floppy_read_wait_index();
        break;

    case ST_read_flux:
    case ST_read_flux_drain:
        floppy_read();
        break;

    case ST_write_flux_wait_data:
        floppy_write_wait_data();
        break;

    case ST_write_flux_wait_index:
        floppy_write_wait_index();
        break;

    case ST_write_flux:
        floppy_write();
        break;

    case ST_write_flux_drain:
        floppy_write_drain();
        break;

    default:
        break;

    }
}

/*
 * INTERRUPT HANDLERS
 */

static void IRQ_INDEX_changed(void)
{
    time_t now = time_now();

    /* Clear INDEX-changed flag. */
    exti->pr = m(pin_index);

    index.count++;
    index.duration = time_diff(index.timestamp, now);
    index.timestamp = now;
    index.read_prod = ARRAY_SIZE(dma.buf) - dma_rdata.cndtr;
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
