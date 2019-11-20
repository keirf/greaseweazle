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
static struct index {
    /* Main code can reset this at will. */
    volatile unsigned int count;
    /* For synchronising index pulse reporting to the RDATA flux stream. */
    volatile unsigned int rdata_cnt;
    /* Following fields are for delayed-index writes. */
    unsigned int delay;
    struct timer delay_timer;
    time_t timestamp;
} index;

#define irq_index_delay 31
void IRQ_31(void) __attribute__((alias("IRQ_INDEX_delay")));
static void index_delay_timer(void *unused);

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

static struct {
    time_t deadline;
    bool_t armed;
} auto_off;

static enum {
    ST_inactive,
    ST_command_wait,
    ST_zlp,
    ST_read_flux,
    ST_read_flux_drain,
    ST_write_flux_wait_data,
    ST_write_flux_wait_index,
    ST_write_flux,
    ST_write_flux_drain,
} floppy_state = ST_inactive;

static uint8_t u_buf[8192];
static uint32_t u_cons, u_prod;
#define U_MASK(x) ((x)&(sizeof(u_buf)-1))

static struct gw_delay delay_params = {
    .select_delay = 10,
    .step_delay = 3000,
    .seek_settle = 15,
    .motor_delay = 750,
    .auto_off = 10000
};

static void step_one_out(void)
{
    write_pin(dir, FALSE);
    delay_us(10);
    write_pin(step, TRUE);
    delay_us(10);
    write_pin(step, FALSE);
    delay_us(delay_params.step_delay);
}

static void step_one_in(void)
{
    write_pin(dir, TRUE);
    delay_us(10);
    write_pin(step, TRUE);
    delay_us(10);
    write_pin(step, FALSE);
    delay_us(delay_params.step_delay);
}

static int cur_cyl = -1;

static void drive_select(bool_t on)
{
    if (read_pin(sel0) == on)
        return;
    write_pin(sel0, on);
    if (on)
        delay_us(delay_params.select_delay);
}

static bool_t floppy_seek(unsigned int cyl)
{
    if ((cyl == 0) || (cur_cyl < 0)) {

        unsigned int i;
        for (i = 0; i < 256; i++) {
            if (get_trk0() == LOW)
                break;
            step_one_out();
        }
        cur_cyl = 0;
        if (get_trk0() == HIGH) {
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

    delay_ms(delay_params.seek_settle);
    cur_cyl = cyl;

    return TRUE;
}

static void drive_motor(bool_t on)
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

static void floppy_reset(void)
{
    unsigned int i;

    floppy_state = ST_inactive;
    auto_off.armed = FALSE;

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

    /* Configure INDEX-changed IRQs and timer. */
    timer_init(&index.delay_timer, index_delay_timer, NULL);
    IRQx_set_prio(irq_index_delay, TIMER_IRQ_PRI);
    IRQx_enable(irq_index_delay);
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

static struct gw_info gw_info = {
    .max_index = 15, .max_cmd = CMD_SELECT,
    .sample_freq = SYSCLK_MHZ * 1000000u
};

static void auto_off_arm(void)
{
    auto_off.armed = TRUE;
    auto_off.deadline = time_now() + time_ms(delay_params.auto_off);
}

static void floppy_end_command(void *ack, unsigned int ack_len)
{
    auto_off_arm();
    usb_write(EP_TX, ack, ack_len);
    u_cons = u_prod = 0;
    if (ack_len == USB_FS_MPS) {
        ASSERT(floppy_state == ST_command_wait);
        floppy_state = ST_zlp;
    }
}

/*
 * READ PATH
 */

static struct {
    time_t start;
    uint8_t status;
    uint8_t idx, nr_idx;
    bool_t packet_ready;
    bool_t write_finished;
    bool_t terminate_at_index;
    bool_t no_flux_area;
    unsigned int packet_len;
    int ticks_since_index;
    uint32_t ticks_since_flux;
    uint32_t index_ticks[15];
    uint8_t packet[USB_FS_MPS];
} rw;

static void rdata_encode_flux(void)
{
    const uint16_t buf_mask = ARRAY_SIZE(dma.buf) - 1;
    uint16_t cons = dma.cons, prod, prev = dma.prev_sample, curr, next;
    uint32_t ticks = rw.ticks_since_flux;
    int ticks_since_index = rw.ticks_since_index;

    ASSERT(rw.idx < rw.nr_idx);

    /* We don't want to race the Index IRQ handler. */
    IRQ_global_disable();

    /* Find out where the DMA engine's producer index has got to. */
    prod = ARRAY_SIZE(dma.buf) - dma_rdata.cndtr;

    if (rw.idx != index.count) {
        /* We have just passed the index mark: Record information about 
         * the just-completed revolution. */
        int partial_flux = ticks + (uint16_t)(index.rdata_cnt - prev);
        rw.index_ticks[rw.idx++] = ticks_since_index + partial_flux;
        ticks_since_index = -partial_flux;
    }

    IRQ_global_enable();

    /* Process the flux timings into the raw bitcell buffer. */
    for (; cons != prod; cons = (cons+1) & buf_mask) {
        next = dma.buf[cons];
        curr = next - prev;
        prev = next;

        ticks += curr;

        if (ticks == 0) {
            /* 0: Skip. */
        } else if (ticks < 250) {
            /* 1-249: One byte. */
            u_buf[U_MASK(u_prod++)] = ticks;
        } else {
            unsigned int high = ticks / 250;
            if (high <= 5) {
                /* 250-1499: Two bytes. */
                u_buf[U_MASK(u_prod++)] = 249 + high;
                u_buf[U_MASK(u_prod++)] = 1 + (ticks % 250);
            } else {
                /* 1500-(2^28-1): Five bytes */
                u_buf[U_MASK(u_prod++)] = 0xff;
                u_buf[U_MASK(u_prod++)] = 1 | (ticks << 1);
                u_buf[U_MASK(u_prod++)] = 1 | (ticks >> 6);
                u_buf[U_MASK(u_prod++)] = 1 | (ticks >> 13);
                u_buf[U_MASK(u_prod++)] = 1 | (ticks >> 20);
            }
        }

        ticks_since_index += ticks;
        ticks = 0;
    }

    /* If it has been a long time since the last flux timing, transfer some of
     * the accumulated time from the 16-bit timestamp into the 32-bit
     * accumulator. This avoids 16-bit overflow and because, we take care to
     * keep the 16-bit timestamp at least 200us behind, we cannot race the next
     * flux timestamp. */
    curr = tim_rdata->cnt - prev;
    if (unlikely(curr > sysclk_us(400))) {
        prev += sysclk_us(200);
        ticks += sysclk_us(200);
    }

    /* Save our progress for next time. */
    dma.cons = cons;
    dma.prev_sample = prev;
    rw.ticks_since_flux = ticks;
    rw.ticks_since_index = ticks_since_index;
}

static uint8_t floppy_read_prep(struct gw_read_flux *rf)
{
    if ((rf->nr_idx == 0) || (rf->nr_idx > gw_info.max_index))
        return ACK_BAD_COMMAND;

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

    /* Start timer. */
    tim_rdata->ccer = TIM_CCER_CC2E | TIM_CCER_CC2P;
    tim_rdata->cr1 = TIM_CR1_CEN;

    index.count = 0;
    floppy_state = ST_read_flux;
    memset(&rw, 0, sizeof(rw));
    rw.nr_idx = rf->nr_idx;
    rw.start = time_now();
    rw.status = ACK_OKAY;

    return ACK_OKAY;
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

        rdata_encode_flux();
        avail = (uint32_t)(u_prod - u_cons);

        if (avail > sizeof(u_buf)) {

            /* Overflow */
            printk("OVERFLOW %u %u %u %u\n", u_cons, u_prod,
                   rw.packet_ready, ep_tx_ready(EP_TX));
            floppy_flux_end();
            rw.status = ACK_FLUX_OVERFLOW;
            floppy_state = ST_read_flux_drain;
            u_cons = u_prod = avail = 0;

        } else if (rw.idx >= rw.nr_idx) {

            /* Read all requested revolutions. */
            floppy_flux_end();
            floppy_state = ST_read_flux_drain;

        } else if ((index.count == 0)
                   && (time_since(rw.start) > time_ms(2000))) {

            /* Timeout */
            printk("NO INDEX\n");
            floppy_flux_end();
            rw.status = ACK_NO_INDEX;
            floppy_state = ST_read_flux_drain;
            u_cons = u_prod = avail = 0;

        }

    } else if ((avail < USB_FS_MPS)
               && !rw.packet_ready
               && ep_tx_ready(EP_TX)) {

        /* Final packet, including ACK byte (NUL). */
        memset(rw.packet, 0, USB_FS_MPS);
        make_read_packet(avail);
        floppy_state = ST_command_wait;
        floppy_end_command(rw.packet, avail+1);
        return; /* FINISHED */

    }

    if (!rw.packet_ready && (avail >= USB_FS_MPS))
        make_read_packet(USB_FS_MPS);

    if (rw.packet_ready && ep_tx_ready(EP_TX)) {
        usb_write(EP_TX, rw.packet, USB_FS_MPS);
        rw.packet_ready = FALSE;
    }
}


/*
 * WRITE PATH
 */

static unsigned int _wdata_decode_flux(uint16_t *tbuf, unsigned int nr)
{
    unsigned int todo = nr;
    uint32_t x, ticks = rw.ticks_since_flux;

    if (todo == 0)
        return 0;

    if (rw.no_flux_area) {
        unsigned int nfa_pulse = sysclk_ns(1250);
        while (ticks >= nfa_pulse) {
            *tbuf++ = nfa_pulse - 1;
            ticks -= nfa_pulse;
            if (!--todo)
                goto out;
        }
        rw.no_flux_area = FALSE;
    }

    while (u_cons != u_prod) {
        x = u_buf[U_MASK(u_cons)];
        if (x == 0) {
            /* 0: Terminate */
            u_cons++;
            rw.write_finished = TRUE;
            goto out;
        } else if (x < 250) {
            /* 1-249: One byte */
            u_cons++;
        } else if (x < 255) {
            /* 250-254: Two bytes */
            if ((uint32_t)(u_prod - u_cons) < 2)
                goto out;
            u_cons++;
            x = (x - 249) * 250;
            x += u_buf[U_MASK(u_cons++)] - 1;
        } else {
            /* 255: Five bytes */
            if ((uint32_t)(u_prod - u_cons) < 5)
                goto out;
            u_cons++;
            x  = (u_buf[U_MASK(u_cons++)]       ) >>  1;
            x |= (u_buf[U_MASK(u_cons++)] & 0xfe) <<  6;
            x |= (u_buf[U_MASK(u_cons++)] & 0xfe) << 13;
            x |= (u_buf[U_MASK(u_cons++)] & 0xfe) << 20;
        }

        ticks += x;
        if (ticks < sysclk_ns(800))
            continue;

        if (ticks > sysclk_us(150)) {
            rw.no_flux_area = TRUE;
            goto out;
        }

        *tbuf++ = ticks - 1;
        ticks = 0;
        if (!--todo)
            goto out;
    }

out:
    rw.ticks_since_flux = ticks;
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
    int len = ep_rx_ready(EP_RX);

    if ((len >= 0) && !rw.packet_ready) {
        usb_read(EP_RX, rw.packet, len);
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

static uint8_t floppy_write_prep(struct gw_write_flux *wf)
{
    if (get_wrprot() == LOW)
        return ACK_WRPROT;

    /* Initialise DMA ring indexes (consumer index is implicit). */
    dma_wdata.cndtr = ARRAY_SIZE(dma.buf);
    dma.prod = 0;

    floppy_state = ST_write_flux_wait_data;
    memset(&rw, 0, sizeof(rw));
    rw.status = ACK_OKAY;

    index.delay = time_sysclk(wf->index_delay_ticks);
    rw.terminate_at_index = wf->terminate_at_index;

    return ACK_OKAY;
}

static void floppy_write_wait_data(void)
{
    bool_t write_finished;

    floppy_process_write_packet();
    wdata_decode_flux();

    /* Wait for DMA and input buffers to fill, or write stream to end. We must
     * take care because, since we are not yet draining the DMA buffer, the
     * write stream may end without us noticing and setting rw.write_finished. 
     * Hence we peek for a NUL byte in the input buffer if it's non-empty. */
    write_finished = ((u_prod == u_cons)
                      ? rw.write_finished
                      : (u_buf[U_MASK(u_prod-1)] == 0));
    if (((dma.prod != (ARRAY_SIZE(dma.buf)-1)) 
         || ((uint32_t)(u_prod - u_cons) < (ARRAY_SIZE(u_buf) - 512)))
        && !write_finished)
        return;

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

    /* Preload timer with first flux value. */
    tim_wdata->egr = TIM_EGR_UG;
    tim_wdata->sr = 0; /* dummy write, gives h/w time to process EGR.UG=1 */

    barrier(); /* Trigger timer update /then/ wait for next index pulse */
    index.count = 0;
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
               rw.packet_ready, ep_rx_ready(EP_RX));
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

    /* Early termination on index pulse? */
    if (rw.terminate_at_index && (index.count != 0))
        goto terminate;

    if (!rw.write_finished) {
        floppy_write_check_underflow();
        return;
    }

    /* Wait for DMA ring to drain. */
    todo = ~0;
    do {
        /* Check for early termination on index pulse. */
        if (rw.terminate_at_index && (index.count != 0))
            goto terminate;
        /* Check progress of draining the DMA ring. */
        prev_todo = todo;
        dmacons = ARRAY_SIZE(dma.buf) - dma_wdata.cndtr;
        todo = (dma.prod - dmacons) & (ARRAY_SIZE(dma.buf) - 1);
    } while ((todo != 0) && (todo <= prev_todo));

terminate:
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
    if (!ep_tx_ready(EP_TX))
        return;

    /* ACK with Status byte. */
    u_buf[0] = rw.status;
    floppy_state = ST_command_wait;
    floppy_end_command(u_buf, 1);

    /* Reset INDEX handling. */
    IRQ_global_disable();
    index.delay = 0;
    IRQx_clear_pending(irq_index_delay);
    timer_cancel(&index.delay_timer);
    IRQ_global_enable();
}

static void process_command(void)
{
    uint8_t cmd = u_buf[0];
    uint8_t len = u_buf[1];
    uint8_t resp_sz = 2;

    auto_off_arm();

    switch (cmd) {
    case CMD_GET_INFO: {
        uint8_t idx = u_buf[2];
        if ((len != 3) || (idx != 0))
            goto bad_command;
        memset(&u_buf[2], 0, 32);
        gw_info.fw_major = fw_major;
        gw_info.fw_minor = fw_minor;
        memcpy(&u_buf[2], &gw_info, sizeof(gw_info));
        resp_sz += 32;
        break;
    }
    case CMD_SEEK: {
        uint8_t cyl = u_buf[2];
        if ((len != 3) || (cyl > 85))
            goto bad_command;
        u_buf[1] = floppy_seek(cyl) ? ACK_OKAY : ACK_NO_TRK0;
        goto out;
    }
    case CMD_SIDE: {
        uint8_t side = u_buf[2];
        if ((len != 3) || (side > 1))
            goto bad_command;
        write_pin(side, side);
        break;
    }
    case CMD_SET_PARAMS: {
        uint8_t idx = u_buf[2];
        if ((len < 3) || (idx != PARAMS_DELAYS)
            || (len > (3 + sizeof(delay_params))))
            goto bad_command;
        memcpy(&delay_params, &u_buf[3], len-3);
        break;
    }
    case CMD_GET_PARAMS: {
        uint8_t idx = u_buf[2];
        uint8_t nr = u_buf[3];
        if ((len != 4) || (idx != PARAMS_DELAYS)
            || (nr > sizeof(delay_params)))
            goto bad_command;
        memcpy(&u_buf[2], &delay_params, nr);
        resp_sz += nr;
        break;
    }
    case CMD_MOTOR: {
        uint8_t mask = u_buf[2];
        if ((len != 3) || (mask & ~1))
            goto bad_command;
        drive_motor(mask & 1);
        break;
    }
    case CMD_READ_FLUX: {
        struct gw_read_flux rf = { .nr_idx = 2 };
        if ((len < 2) || (len > (2 + sizeof(rf))))
            goto bad_command;
        memcpy(&rf, &u_buf[2], len-2);
        u_buf[1] = floppy_read_prep(&rf);
        goto out;
    }
    case CMD_WRITE_FLUX: {
        struct gw_write_flux wf = { 0 };
        if ((len < 2) || (len > (2 + sizeof(wf))))
            goto bad_command;
        memcpy(&wf, &u_buf[2], len-2);
        u_buf[1] = floppy_write_prep(&wf);
        goto out;

    }
    case CMD_GET_FLUX_STATUS: {
        if (len != 2)
            goto bad_command;
        u_buf[1] = rw.status;
        goto out;
    }
    case CMD_GET_INDEX_TIMES: {
        uint8_t f = u_buf[2], n = u_buf[3];
        if ((len != 4) || (n > 15) || ((f+n) > gw_info.max_index))
            goto bad_command;
        memcpy(&u_buf[2], rw.index_ticks+f, n*4);
        resp_sz += n*4;
        break;
    }
    case CMD_SELECT: {
        uint8_t mask = u_buf[2];
        if ((len != 3) || (mask & ~1))
            goto bad_command;
        drive_select(mask & 1);
        break;
    }
    default:
        goto bad_command;
    }

    u_buf[1] = ACK_OKAY;
out:
    floppy_end_command(u_buf, resp_sz);
    return;

bad_command:
    u_buf[1] = ACK_BAD_COMMAND;
    goto out;
}

static void floppy_configure(void)
{
    auto_off_arm();
    floppy_flux_end();
    floppy_state = ST_command_wait;
    u_cons = u_prod = 0;
}

void floppy_process(void)
{
    int len;

    if (auto_off.armed && (time_since(auto_off.deadline) >= 0)) {
        floppy_flux_end();
        drive_motor(FALSE);
        drive_select(FALSE);
        auto_off.armed = FALSE;
        //gpio_write_pin(gpioa, 0, LOW);
        //delay_ms(100); /* force disconnect */
        //gpio_write_pin(gpioa, 0, HIGH);
    }

    switch (floppy_state) {

    case ST_command_wait:

        len = ep_rx_ready(EP_RX);
        if ((len >= 0) && (len < (sizeof(u_buf)-u_prod))) {
            usb_read(EP_RX, &u_buf[u_prod], len);
            u_prod += len;
        }

        if ((u_prod >= 2) && (u_prod >= u_buf[1]) && ep_tx_ready(EP_TX)) {
            process_command();
        }

        break;

    case ST_zlp:
        if (ep_tx_ready(EP_TX)) {
            usb_write(EP_TX, NULL, 0);
            floppy_state = ST_command_wait;
        }
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

const struct usb_class_ops usb_cdc_acm_ops = {
    .reset = floppy_reset,
    .configure = floppy_configure
};

/*
 * INTERRUPT HANDLERS
 */

static void index_delay_timer(void *unused)
{
    index.count++;
}

static void IRQ_INDEX_delay(void)
{
    timer_set(&index.delay_timer, index.timestamp + index.delay);
}

static void IRQ_INDEX_changed(void)
{
    /* Clear INDEX-changed flag. */
    exti->pr = m(pin_index);

    index.rdata_cnt = tim_rdata->cnt;
    index.timestamp = time_now();

    if (index.delay != 0) {
        IRQx_set_pending(irq_index_delay);
    } else {
        index.count++;
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
