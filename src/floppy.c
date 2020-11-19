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

#define m(bitnr) (1u<<(bitnr))

#define get_index()   gpio_read_pin(gpio_index, pin_index)
#define get_trk0()    gpio_read_pin(gpio_trk0, pin_trk0)
#define get_wrprot()  gpio_read_pin(gpio_wrprot, pin_wrprot)

#define configure_pin(pin, type) \
    gpio_configure_pin(gpio_##pin, pin_##pin, type)

#define SAMPLE_MHZ 72
#define TIM_PSC (SYSCLK_MHZ / SAMPLE_MHZ)
#define sample_ns(x) (((x) * SAMPLE_MHZ) / 1000)
#define sample_us(x) ((x) * SAMPLE_MHZ)
#define time_from_samples(x) ((x) * TIME_MHZ / SAMPLE_MHZ)

#define write_pin(pin, level) \
    gpio_write_pin(gpio_##pin, pin_##pin, level ? O_TRUE : O_FALSE)

static int bus_type = -1;
static int unit_nr = -1;
static struct unit {
    int cyl;
    bool_t initialised;
    bool_t is_flippy;
    bool_t motor;
} unit[3];

static struct gw_delay delay_params;
static const struct gw_delay factory_delay_params = {
    .select_delay = 10,
    .step_delay = 5000,
    .seek_settle = 15,
    .motor_delay = 750,
    .auto_off = 10000
};

#if STM32F == 1
#include "f1/floppy.c"
#elif STM32F == 7
#include "f7/floppy.c"
#endif

static struct index {
    /* Main code can reset this at will. */
    volatile unsigned int count;
    /* For synchronising index pulse reporting to the RDATA flux stream. */
    volatile unsigned int rdata_cnt;
    /* Last time at which ISR fired. */
    time_t isr_time;
    /* Timer structure for index_timer() calls. */
    struct timer timer;
} index;

/* Timer to clean up stale index.isr_time. */
#define INDEX_TIMER_PERIOD time_ms(5000)
static void index_timer(void *unused);

/* A DMA buffer for running a timer associated with a floppy-data I/O pin. */
static struct dma_ring {
    /* Indexes into the buf[] ring buffer. */
    uint16_t cons; /* dma_rd: our consumer index for flux samples */
    union {
        uint16_t prod; /* dma_wr: our producer index for flux samples */
        timcnt_t prev_sample; /* dma_rd: previous CCRx sample value */
    };
    /* DMA ring buffer of timer values (ARR or CCRx). */
    timcnt_t buf[512];
} dma;

static struct {
    time_t deadline;
    bool_t armed;
} auto_off;

/* Marshalling and unmarshalling of USB packets. */
static struct {
    /* TRUE if a packet is ready: .data and .len are valid. */
    bool_t ready;
    /* Length and contents of the packet (if ready==TRUE). */
    unsigned int len;
    uint8_t data[USB_HS_MPS];
} usb_packet;

/* Read, write, erase: Shared command state. */
static struct {
    union {
        time_t start; /* read, write: Time at which read/write started. */
        time_t end;   /* erase: Time at which to end the erasure. */
    };
    uint8_t status;
} flux_op;

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
    ST_erase_flux,
    ST_source_bytes,
    ST_sink_bytes,
    ST_update_bootloader,
} floppy_state = ST_inactive;

static uint32_t u_cons, u_prod;
#define U_MASK(x) ((x)&(U_BUF_SZ-1))

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

static void _set_bus_type(uint8_t type)
{
    bus_type = type;
    unit_nr = -1;
    memset(unit, 0, sizeof(unit));
    reset_bus();
}

static bool_t set_bus_type(uint8_t type)
{
    if (type == bus_type)
        return TRUE;

    if (type > BUS_SHUGART)
        return FALSE;

    _set_bus_type(type);

    return TRUE;
}

static uint8_t floppy_seek(int cyl)
{
    struct unit *u;

    if (unit_nr < 0)
        return ACK_NO_UNIT;
    u = &unit[unit_nr];

    if (!u->initialised) {
        unsigned int i;
        for (i = 0; i < 256; i++) {
            if (get_trk0() == LOW)
                goto found_trk0;
            step_one_out();
        }
        return ACK_NO_TRK0;
    found_trk0:
        u->is_flippy = flippy_detect();
        u->initialised = TRUE;
        u->cyl = 0;
    }

    if ((cyl < (u->is_flippy ? -8 : 0)) || (cyl > 100))
        return ACK_BAD_CYLINDER;

    flippy_trk0_sensor_disable();

    if (u->cyl <= cyl) {

        int nr = cyl - u->cyl;
        while (nr--)
            step_one_in();

    } else {

        int nr = u->cyl - cyl;
        while (nr--)
            step_one_out();

    }

    flippy_trk0_sensor_enable();

    delay_ms(delay_params.seek_settle);
    u->cyl = cyl;

    return ACK_OKAY;
}

static void floppy_flux_end(void)
{
    /* Turn off write pins. */
    write_pin(wgate, FALSE);
    configure_pin(wdata, GPO_bus);    

    /* Turn off timers. */
    tim_rdata->ccer = 0;
    tim_rdata->cr1 = 0;
    tim_rdata->sr = 0; /* dummy, drains any pending DMA */
    tim_wdata->ccer = 0;
    tim_wdata->cr1 = 0;
    tim_wdata->sr = 0; /* dummy, drains any pending DMA */

    /* Turn off DMA. */
    dma_rdata.cr &= ~DMA_CR_EN;
    dma_wdata.cr &= ~DMA_CR_EN;
    while ((dma_rdata.cr & DMA_CR_EN) || (dma_wdata.cr & DMA_CR_EN))
        continue;
}

static void do_auto_off(void)
{
    int i;

    floppy_flux_end();

    for (i = 0; i < ARRAY_SIZE(unit); i++) {

        struct unit *u = &unit[i];
        if (!u->initialised)
            continue;

        if (u->cyl < 0) {
            drive_select(i);
            floppy_seek(0);
        }

        if (u->motor)
            drive_motor(i, FALSE);

    }

    drive_deselect();

    auto_off.armed = FALSE;
}

static void floppy_reset(void)
{
    floppy_state = ST_inactive;
    do_auto_off();
    act_led(FALSE);
}

void floppy_init(void)
{
    floppy_mcu_init();

    /* Output pins, unbuffered. */
    configure_pin(dir,    GPO_bus);
    configure_pin(step,   GPO_bus);
    configure_pin(wgate,  GPO_bus);
    configure_pin(side,   GPO_bus);
    configure_pin(wdata,  GPO_bus);

    /* Input pins. */
    configure_pin(index,  GPI_bus);
    configure_pin(trk0,   GPI_bus);
    configure_pin(wrprot, GPI_bus);

    /* Configure INDEX-changed IRQs and timer. */
    timer_init(&index.timer, index_timer, NULL);
    index_timer(NULL);
    exti->rtsr = 0;
    exti->imr = exti->ftsr = m(pin_index);
    IRQx_set_prio(irq_index, INDEX_IRQ_PRI);
    IRQx_enable(irq_index);

    delay_params = factory_delay_params;

    _set_bus_type(BUS_NONE);
}

struct gw_info gw_info = {
    .is_main_firmware = 1,
    .max_cmd = CMD_MAX,
    .sample_freq = 72000000u,
    .hw_model = STM32F
};

static void auto_off_nudge(void)
{
    auto_off.deadline = time_now() + time_ms(delay_params.auto_off);
}

static void auto_off_arm(void)
{
    auto_off.armed = TRUE;
    auto_off_nudge();
}

static void floppy_end_command(void *ack, unsigned int ack_len)
{
    auto_off_arm();
    usb_write(EP_TX, ack, ack_len);
    u_cons = u_prod = 0;
    if (floppy_state == ST_command_wait)
        act_led(FALSE);
    if (ack_len == usb_bulk_mps) {
        ASSERT(floppy_state == ST_command_wait);
        floppy_state = ST_zlp;
    }
}

/*
 * READ PATH
 */

static struct {
    unsigned int idx, nr_idx;
} read;

static void _write_28bit(uint32_t x)
{
    u_buf[U_MASK(u_prod++)] = 1 | (x << 1);
    u_buf[U_MASK(u_prod++)] = 1 | (x >> 6);
    u_buf[U_MASK(u_prod++)] = 1 | (x >> 13);
    u_buf[U_MASK(u_prod++)] = 1 | (x >> 20);
}

static void rdata_encode_flux(void)
{
    const uint16_t buf_mask = ARRAY_SIZE(dma.buf) - 1;
    uint16_t cons = dma.cons, prod;
    timcnt_t prev = dma.prev_sample, curr, next;
    uint32_t ticks;

    ASSERT(read.idx < read.nr_idx);

    /* We don't want to race the Index IRQ handler. */
    IRQ_global_disable();

    /* Find out where the DMA engine's producer index has got to. */
    prod = ARRAY_SIZE(dma.buf) - dma_rdata.ndtr;

    if (read.idx != index.count) {
        /* We have just passed the index mark: Record information about 
         * the just-completed revolution. */
        read.idx = index.count;
        ticks = (timcnt_t)(index.rdata_cnt - prev);
        IRQ_global_enable(); /* we're done reading ISR variables */
        u_buf[U_MASK(u_prod++)] = 0xff;
        u_buf[U_MASK(u_prod++)] = FLUXOP_INDEX;
        _write_28bit(ticks);
        /* Defer auto-off while read is progressing (as measured by index
         * pulses).  */
        auto_off_nudge();
    }

    IRQ_global_enable();

    /* Process the flux timings into the raw bitcell buffer. */
    for (; cons != prod; cons = (cons+1) & buf_mask) {
        next = dma.buf[cons];
        curr = next - prev;
        prev = next;

        ticks = curr;

        if (ticks == 0) {
            /* 0: Skip. */
        } else if (ticks < 250) {
            /* 1-249: One byte. */
            u_buf[U_MASK(u_prod++)] = ticks;
        } else {
            unsigned int high = (ticks-250) / 255;
            if (high < 5) {
                /* 250-1524: Two bytes. */
                u_buf[U_MASK(u_prod++)] = 250 + high;
                u_buf[U_MASK(u_prod++)] = 1 + ((ticks-250) % 255);
            } else {
                /* 1525-(2^28-1): Seven bytes. */
                u_buf[U_MASK(u_prod++)] = 0xff;
                u_buf[U_MASK(u_prod++)] = FLUXOP_SPACE;
                _write_28bit(ticks - 249);
                u_buf[U_MASK(u_prod++)] = 249;
            }
        }
    }

    /* If it has been a long time since the last flux timing, transfer some of
     * the accumulated time to the host in a "long gap" sample. This avoids
     * timing overflow and, because we take care to keep @prev well behind the
     * sample clock, we cannot race the next flux timestamp. */
    curr = tim_rdata->cnt - prev;
    if (unlikely(curr > sample_us(400))) {
        ticks = sample_us(200);
        u_buf[U_MASK(u_prod++)] = 0xff;
        u_buf[U_MASK(u_prod++)] = FLUXOP_SPACE;
        _write_28bit(ticks);
        prev += ticks;
    }

    /* Save our progress for next time. */
    dma.cons = cons;
    dma.prev_sample = prev;
}

static uint8_t floppy_read_prep(const struct gw_read_flux *rf)
{
    if (rf->nr_idx == 0)
        return ACK_BAD_COMMAND;

    /* Prepare Timer & DMA. */
    dma_rdata.mar = (uint32_t)(unsigned long)dma.buf;
    dma_rdata.ndtr = ARRAY_SIZE(dma.buf);    
    rdata_prep();

    /* DMA soft state. */
    dma.cons = 0;
    dma.prev_sample = tim_rdata->cnt;

    /* Start Timer. */
    tim_rdata->cr1 = TIM_CR1_CEN;

    index.count = 0;
    usb_packet.ready = FALSE;

    floppy_state = ST_read_flux;
    flux_op.start = time_now();
    flux_op.status = ACK_OKAY;
    memset(&read, 0, sizeof(read));
    read.nr_idx = rf->nr_idx;

    return ACK_OKAY;
}

static void make_read_packet(unsigned int n)
{
    unsigned int c = U_MASK(u_cons);
    unsigned int l = U_BUF_SZ - c;
    if (l < n) {
        memcpy(usb_packet.data, &u_buf[c], l);
        memcpy(&usb_packet.data[l], u_buf, n-l);
    } else {
        memcpy(usb_packet.data, &u_buf[c], n);
    }
    u_cons += n;
    usb_packet.ready = TRUE;
    usb_packet.len = n;
}

static void floppy_read(void)
{
    unsigned int avail = (uint32_t)(u_prod - u_cons);

    if (floppy_state == ST_read_flux) {

        rdata_encode_flux();
        avail = (uint32_t)(u_prod - u_cons);

        if (avail > U_BUF_SZ) {

            /* Overflow */
            printk("OVERFLOW %u %u %u %u\n", u_cons, u_prod,
                   usb_packet.ready, ep_tx_ready(EP_TX));
            floppy_flux_end();
            flux_op.status = ACK_FLUX_OVERFLOW;
            floppy_state = ST_read_flux_drain;
            u_cons = u_prod = avail = 0;

        } else if (read.idx >= read.nr_idx) {

            /* Read all requested revolutions. */
            floppy_flux_end();
            floppy_state = ST_read_flux_drain;

        } else if ((index.count == 0)
                   && (time_since(flux_op.start) > time_ms(2000))) {

            /* Timeout */
            printk("NO INDEX\n");
            floppy_flux_end();
            flux_op.status = ACK_NO_INDEX;
            floppy_state = ST_read_flux_drain;
            u_cons = u_prod = avail = 0;

        }

    } else if ((avail < usb_bulk_mps)
               && !usb_packet.ready
               && ep_tx_ready(EP_TX)) {

        /* Final packet, including ACK byte (NUL). */
        memset(usb_packet.data, 0, usb_bulk_mps);
        make_read_packet(avail);
        floppy_state = ST_command_wait;
        floppy_end_command(usb_packet.data, avail+1);
        return; /* FINISHED */

    }

    if (!usb_packet.ready && (avail >= usb_bulk_mps))
        make_read_packet(usb_bulk_mps);

    if (usb_packet.ready && ep_tx_ready(EP_TX)) {
        usb_write(EP_TX, usb_packet.data, usb_packet.len);
        usb_packet.ready = FALSE;
    }
}


/*
 * WRITE PATH
 */

static struct {
    bool_t is_finished;
    bool_t terminate_at_index;
    uint32_t astable_period;
    uint32_t ticks;
    enum {
        FLUXMODE_idle,    /* generating no flux (awaiting next command) */
        FLUXMODE_oneshot, /* generating a single flux */
        FLUXMODE_astable  /* generating a region of oscillating flux */
    } flux_mode;
} write;

static uint32_t _read_28bit(void)
{
    uint32_t x;
    x  = (u_buf[U_MASK(u_cons++)]       ) >>  1;
    x |= (u_buf[U_MASK(u_cons++)] & 0xfe) <<  6;
    x |= (u_buf[U_MASK(u_cons++)] & 0xfe) << 13;
    x |= (u_buf[U_MASK(u_cons++)] & 0xfe) << 20;
    return x;
}

static unsigned int _wdata_decode_flux(timcnt_t *tbuf, unsigned int nr)
{
#define MIN_PULSE sample_ns(800)

    unsigned int todo = nr;
    uint32_t x, ticks = write.ticks;

    if (todo == 0)
        return 0;

    switch (write.flux_mode) {

    case FLUXMODE_astable: {
        /* Produce flux transitions at the specified period. */
        uint32_t pulse = write.astable_period;
        while (ticks >= pulse) {
            *tbuf++ = pulse - 1;
            ticks -= pulse;
            if (!--todo)
                goto out;
        }
        write.flux_mode = FLUXMODE_idle;
        break;
    }

    case FLUXMODE_oneshot:
        /* If ticks to next flux would overflow the hardware counter, insert
         * extra fluxes as necessary to get us to the proper next flux. */
        while (ticks != (timcnt_t)ticks) {
            uint32_t pulse = (timcnt_t)-1 + 1;
            *tbuf++ = pulse - 1;
            ticks -= pulse;
            if (!--todo)
                goto out;
        }

        /* Process the one-shot unless it's too short, in which case
         * it will be merged into the next region. */
        if (ticks > MIN_PULSE) {
            *tbuf++ = ticks - 1;
            ticks = 0;
            if (!--todo)
                goto out;
        }

        write.flux_mode = FLUXMODE_idle;
        break;

    case FLUXMODE_idle:
        /* Nothing to do (waiting for a flux command). */
        break;

    }

    while (u_cons != u_prod) {

        ASSERT(write.flux_mode == FLUXMODE_idle);

        x = u_buf[U_MASK(u_cons)];
        if (x == 0) {
            /* 0: Terminate */
            u_cons++;
            write.is_finished = TRUE;
            goto out;
        } else if (x < 250) {
            /* 1-249: One byte. Time to next flux.*/
            u_cons++;
        } else if (x < 255) {
            /* 250-254: Two bytes. Time to next flux. */
            if ((uint32_t)(u_prod - u_cons) < 2)
                goto out;
            u_cons++;
            x = 250 + (x - 250) * 255;
            x += u_buf[U_MASK(u_cons++)] - 1;
        } else {
            /* 255: Six bytes */
            uint8_t op;
            if ((uint32_t)(u_prod - u_cons) < 6)
                goto out;
            op = u_buf[U_MASK(u_cons+1)];
            u_cons += 2;
            switch (op) {
            case FLUXOP_SPACE:
                ticks += _read_28bit();
                continue;
            case FLUXOP_ASTABLE: {
                uint32_t period = _read_28bit();
                if ((period < MIN_PULSE) || (period != (timcnt_t)period)) {
                    /* Bad period value: underflow or overflow. */
                    goto error;
                }
                write.astable_period = period;
                write.flux_mode = FLUXMODE_astable;
                goto out;
            }
            default:
                /* Invalid opcode */
                u_cons += 4;
                goto error;
            }
        }

        /* We're now implicitly in FLUXMODE_oneshot, but we don't register it 
         * explicitly as we usually switch straight back to FLUXMODE_idle. */
        ticks += x;

        /* This sample too small? Then ignore this flux transition. */
        if (ticks < MIN_PULSE)
            continue;

        /* This sample overflows the hardware timer's counter width?
         * Then bail, and we'll split it into chunks. */
        if (ticks != (timcnt_t)ticks) {
            write.flux_mode = FLUXMODE_oneshot;
            goto out;
        }

        *tbuf++ = ticks - 1;
        ticks = 0;
        if (!--todo)
            goto out;
    }

out:
    write.ticks = ticks;
    return nr - todo;

error:
    floppy_flux_end();
    flux_op.status = ACK_BAD_COMMAND;
    floppy_state = ST_write_flux_drain;
    goto out;
}

static void wdata_decode_flux(void)
{
    const uint16_t buf_mask = ARRAY_SIZE(dma.buf) - 1;
    uint16_t nr_to_wrap, nr_to_cons, nr, dmacons;

    /* Find out where the DMA engine's consumer index has got to. */
    dmacons = ARRAY_SIZE(dma.buf) - dma_wdata.ndtr;

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

    if ((len >= 0) && !usb_packet.ready) {
        usb_read(EP_RX, usb_packet.data, len);
        usb_packet.ready = TRUE;
        usb_packet.len = len;
    }

    if (usb_packet.ready) {
        unsigned int avail = U_BUF_SZ - (uint32_t)(u_prod - u_cons);
        unsigned int n = usb_packet.len;
        if (avail >= n) {
            unsigned int p = U_MASK(u_prod);
            unsigned int l = U_BUF_SZ - p;
            if (l < n) {
                memcpy(&u_buf[p], usb_packet.data, l);
                memcpy(u_buf, &usb_packet.data[l], n-l);
            } else {
                memcpy(&u_buf[p], usb_packet.data, n);
            }
            u_prod += n;
            usb_packet.ready = FALSE;
        }
    }
}

static uint8_t floppy_write_prep(const struct gw_write_flux *wf)
{
    if (get_wrprot() == LOW)
        return ACK_WRPROT;

    wdata_prep();

    /* WDATA DMA setup: From a circular buffer into the WDATA Timer's ARR. */
    dma_wdata.par = (uint32_t)(unsigned long)&tim_wdata->arr;
    dma_wdata.mar = (uint32_t)(unsigned long)dma.buf;

    /* Initialise DMA ring indexes (consumer index is implicit). */
    dma_wdata.ndtr = ARRAY_SIZE(dma.buf);
    dma.prod = 0;

    usb_packet.ready = FALSE;

    floppy_state = ST_write_flux_wait_data;
    flux_op.status = ACK_OKAY;
    memset(&write, 0, sizeof(write));
    write.flux_mode = FLUXMODE_idle;
    write.terminate_at_index = wf->terminate_at_index;

    return ACK_OKAY;
}

static void floppy_write_wait_data(void)
{
    bool_t write_finished;
    unsigned int u_buf_threshold;

    floppy_process_write_packet();
    wdata_decode_flux();
    if (flux_op.status != ACK_OKAY)
        return;

    /* We don't wait for the massive F7 u_buf[] to fill at Full Speed. */
    u_buf_threshold = ((U_BUF_SZ > 16384) && !usb_is_highspeed())
        ? 16384 - 512 : U_BUF_SZ - 512;

    /* Wait for DMA and input buffers to fill, or write stream to end. We must
     * take care because, since we are not yet draining the DMA buffer, the
     * write stream may end without us noticing and setting write.is_finished. 
     * Hence we peek for a NUL byte in the input buffer if it's non-empty. */
    write_finished = ((u_prod == u_cons)
                      ? write.is_finished
                      : (u_buf[U_MASK(u_prod-1)] == 0));
    if (((dma.prod != (ARRAY_SIZE(dma.buf)-1)) 
         || ((uint32_t)(u_prod - u_cons) < u_buf_threshold))
        && !write_finished)
        return;

    floppy_state = ST_write_flux_wait_index;
    flux_op.start = time_now();

    /* Enable DMA only after flux values are generated. */
    dma_wdata_start();

    /* Preload timer with first flux value. */
    tim_wdata->egr = TIM_EGR_UG;
    tim_wdata->sr = 0; /* dummy write, gives h/w time to process EGR.UG=1 */

    barrier(); /* Trigger timer update /then/ wait for next index pulse */
    index.count = 0;
}

static void floppy_write_wait_index(void)
{
    if (index.count == 0) {
        if (time_since(flux_op.start) > time_ms(2000)) {
            /* Timeout */
            floppy_flux_end();
            flux_op.status = ACK_NO_INDEX;
            floppy_state = ST_write_flux_drain;
        }
        return;
    }

    /* Start timer. */
    tim_wdata->cr1 = TIM_CR1_CEN;

    /* Enable output. */
    configure_pin(wdata, AFO_bus);
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
               usb_packet.ready, ep_rx_ready(EP_RX));
        floppy_flux_end();
        flux_op.status = ACK_FLUX_UNDERFLOW;
        floppy_state = ST_write_flux_drain;

    }
}

static void floppy_write(void)
{
    uint16_t dmacons, todo, prev_todo;

    floppy_process_write_packet();
    wdata_decode_flux();
    if (flux_op.status != ACK_OKAY)
        return;

    /* Early termination on index pulse? */
    if (write.terminate_at_index && (index.count != 0))
        goto terminate;

    if (!write.is_finished) {
        floppy_write_check_underflow();
        return;
    }

    /* Wait for DMA ring to drain. */
    todo = ~0;
    do {
        /* Check for early termination on index pulse. */
        if (write.terminate_at_index && (index.count != 0))
            goto terminate;
        /* Check progress of draining the DMA ring. */
        prev_todo = todo;
        dmacons = ARRAY_SIZE(dma.buf) - dma_wdata.ndtr;
        todo = (dma.prod - dmacons) & (ARRAY_SIZE(dma.buf) - 1);
    } while ((todo != 0) && (todo <= prev_todo));

terminate:
    floppy_flux_end();
    floppy_state = ST_write_flux_drain;
}

static void floppy_write_drain(void)
{
    /* Drain the write stream. */
    if (!write.is_finished) {
        floppy_process_write_packet();
        (void)_wdata_decode_flux(dma.buf, ARRAY_SIZE(dma.buf));
        return;
    }

    /* Wait for space to write ACK usb_packet. */
    if (!ep_tx_ready(EP_TX))
        return;

    /* ACK with Status byte. */
    u_buf[0] = flux_op.status;
    floppy_state = ST_command_wait;
    floppy_end_command(u_buf, 1);
}


/*
 * ERASE PATH
 */

static uint8_t floppy_erase_prep(const struct gw_erase_flux *ef)
{
    if (get_wrprot() == LOW)
        return ACK_WRPROT;

    write_pin(wgate, TRUE);

    floppy_state = ST_erase_flux;
    flux_op.status = ACK_OKAY;
    flux_op.end = time_now() + time_from_samples(ef->erase_ticks);

    return ACK_OKAY;
}

static void floppy_erase(void)
{
    if (time_since(flux_op.end) < 0)
        return;

    write_pin(wgate, FALSE);

    /* ACK with Status byte. */
    u_buf[0] = flux_op.status;
    floppy_state = ST_command_wait;
    floppy_end_command(u_buf, 1);
}


/*
 * SINK/SOURCE
 */

static struct {
    unsigned int todo;
    unsigned int min_delta;
    unsigned int max_delta;
} ss;

static void sink_source_prep(const struct gw_sink_source_bytes *ssb)
{
    ss.min_delta = INT_MAX;
    ss.max_delta = 0;
    ss.todo = ssb->nr_bytes;
}

static void ss_update_deltas(int len)
{
    uint32_t *u_times = (uint32_t *)u_buf;
    time_t delta, now = time_now();
    unsigned int p = u_prod;

    /* Every four bytes we store a timestamp in a u_buf[]-sized ring buffer.
     * We then record min/max time taken to overwrite a previous timestamp. */
    while (len--) {
        if (p++ & 3)
            continue;
        delta = time_diff(u_times[U_MASK(p)>>2], now);
        u_times[U_MASK(p)>>2] = now;
        if ((delta > ss.max_delta) && (p >= U_BUF_SZ))
            ss.max_delta = delta;
        if ((delta < ss.min_delta) && (p >= U_BUF_SZ))
            ss.min_delta = delta;
    }

    u_prod = p;
}

static void source_bytes(void)
{
    if (!ep_tx_ready(EP_TX))
        return;

    if (ss.todo < usb_bulk_mps) {
        floppy_state = ST_command_wait;
        floppy_end_command(usb_packet.data, ss.todo);
        return; /* FINISHED */
    }

    usb_write(EP_TX, usb_packet.data, usb_bulk_mps);
    ss.todo -= usb_bulk_mps;
    ss_update_deltas(usb_bulk_mps);
}

static void sink_bytes(void)
{
    int len;

    if (ss.todo == 0) {
        /* We're done: Wait for space to write the ACK byte. */
        if (!ep_tx_ready(EP_TX))
            return;
        u_buf[0] = ACK_OKAY;
        floppy_state = ST_command_wait;
        floppy_end_command(u_buf, 1);
        return; /* FINISHED */
    }

    /* Packet ready? */
    len = ep_rx_ready(EP_RX);
    if (len < 0)
        return;

    /* Read it and adjust byte counter. */
    usb_read(EP_RX, usb_packet.data, len);
    ss.todo = (ss.todo <= len) ? 0 : ss.todo - len;
    ss_update_deltas(len);
}


/*
 * BOOTLOADER UPDATE
 */

#define BL_START 0x08000000
#define BL_END   ((uint32_t)_stext)
#define BL_SIZE  (BL_END - BL_START)

static struct {
    uint32_t len;
    uint32_t cur;
} update;

static void erase_old_bootloader(void)
{
    uint32_t p;
    for (p = BL_START; p < BL_END; p += FLASH_PAGE_SIZE)
        fpec_page_erase(p);
}

static void update_prep(uint32_t len)
{
    fpec_init();
    erase_old_bootloader();

    floppy_state = ST_update_bootloader;
    update.cur = 0;
    update.len = len;

    printk("Update Bootloader: %u bytes\n", len);
}

static void update_continue(void)
{
    int len;

    if ((len = ep_rx_ready(EP_RX)) >= 0) {
        usb_read(EP_RX, &u_buf[u_prod], len);
        u_prod += len;
    }

    if ((len = u_prod) >= 2) {
        int nr = len & ~1;
        fpec_write(u_buf, nr, BL_START + update.cur);
        update.cur += nr;
        u_prod -= nr;
        memcpy(u_buf, &u_buf[nr], u_prod);
    }

    if ((update.cur >= update.len) && ep_tx_ready(EP_TX)) {
        uint16_t crc = crc16_ccitt((void *)BL_START, update.len, 0xffff);
        printk("Final CRC: %04x (%s)\n", crc, crc ? "FAIL" : "OK");
        u_buf[0] = !!crc;
        floppy_state = ST_command_wait;
        floppy_end_command(u_buf, 1);
    }
}


static void process_command(void)
{
    uint8_t cmd = u_buf[0];
    uint8_t len = u_buf[1];
    uint8_t resp_sz = 2;

    auto_off_arm();
    act_led(TRUE);

    switch (cmd) {
    case CMD_GET_INFO: {
        uint8_t idx = u_buf[2];
        if (len != 3)
            goto bad_command;
        memset(&u_buf[2], 0, 32);
        switch(idx) {
        case GETINFO_FIRMWARE: /* gw_info */
            gw_info.fw_major = fw_major;
            gw_info.fw_minor = fw_minor;
            memcpy(&u_buf[2], &gw_info, sizeof(gw_info));
            break;
        case GETINFO_BW_STATS: /* gw_bw_stats */ {
            struct gw_bw_stats bw;
            bw.min_bw.bytes = U_BUF_SZ;
            bw.min_bw.usecs = ss.max_delta / time_us(1);
            bw.max_bw.bytes = U_BUF_SZ;
            bw.max_bw.usecs = ss.min_delta / time_us(1);
            memcpy(&u_buf[2], &bw, sizeof(bw));
            break;
        }
        default:
            goto bad_command;
        }
        resp_sz += 32;
        break;
    }
    case CMD_UPDATE: {
        uint32_t u_len = *(uint32_t *)&u_buf[2];
        uint32_t signature = *(uint32_t *)&u_buf[6];
        if (len != 10) goto bad_command;
        if (u_len & 3) goto bad_command;
        if (u_len > BL_SIZE) goto bad_command;
        if (signature != 0xdeafbee3) goto bad_command;
        update_prep(u_len);
        break;
    }
    case CMD_SEEK: {
        int8_t cyl = u_buf[2];
        if (len != 3)
            goto bad_command;
        u_buf[1] = floppy_seek(cyl);
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
        uint8_t unit = u_buf[2], on_off = u_buf[3];
        if ((len != 4) || (on_off & ~1))
            goto bad_command;
        u_buf[1] = drive_motor(unit, on_off & 1);
        goto out;
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
        u_buf[1] = flux_op.status;
        goto out;
    }
    case CMD_SELECT: {
        uint8_t unit = u_buf[2];
        if (len != 3)
            goto bad_command;
        u_buf[1] = drive_select(unit);
        goto out;
    }
    case CMD_DESELECT: {
        if (len != 2)
            goto bad_command;
        drive_deselect();
        break;
    }
    case CMD_SET_BUS_TYPE: {
        uint8_t type = u_buf[2];
        if ((len != 3) || !set_bus_type(type))
            goto bad_command;
        break;
    }
    case CMD_SET_PIN: {
        uint8_t pin = u_buf[2];
        uint8_t level = u_buf[3];
        if ((len != 4) || (level & ~1))
            goto bad_command;
        u_buf[1] = set_user_pin(pin, level);
        goto out;
    }
    case CMD_RESET: {
        if (len != 2)
            goto bad_command;
        delay_params = factory_delay_params;
        _set_bus_type(BUS_NONE);
        reset_user_pins();
        break;
    }
    case CMD_ERASE_FLUX: {
        struct gw_erase_flux ef;
        if (len != (2 + sizeof(ef)))
            goto bad_command;
        memcpy(&ef, &u_buf[2], len-2);
        u_buf[1] = floppy_erase_prep(&ef);
        goto out;
    }
    case CMD_SOURCE_BYTES:
    case CMD_SINK_BYTES: {
        struct gw_sink_source_bytes ssb;
        if (len != (2 + sizeof(ssb)))
            goto bad_command;
        memcpy(&ssb, &u_buf[2], len-2);
        floppy_state = (cmd == CMD_SOURCE_BYTES)
            ? ST_source_bytes : ST_sink_bytes;
        sink_source_prep(&ssb);
        break;
    }
#if STM32F == 7
    case CMD_SWITCH_FW_MODE: {
        uint8_t mode = u_buf[2];
        if ((len != 3) || (mode & ~1))
            goto bad_command;
        if (mode == FW_MODE_BOOTLOADER) {
            usb_deinit();
            delay_ms(500);
            /* Poke a flag in SRAM1, picked up by the bootloader. */
            *(volatile uint32_t *)0x20010000 = 0xdeadbeef;
            dcache_disable();
            system_reset();
        }
        break;
    }
#endif
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
    act_led(FALSE);
}

void floppy_process(void)
{
    int len;

    if (auto_off.armed && (time_since(auto_off.deadline) >= 0))
        do_auto_off();

    switch (floppy_state) {

    case ST_command_wait:

        len = ep_rx_ready(EP_RX);
        if ((len >= 0) && (len < (U_BUF_SZ-u_prod))) {
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

    case ST_erase_flux:
        floppy_erase();
        break;

    case ST_source_bytes:
        source_bytes();
        break;

    case ST_sink_bytes:
        sink_bytes();
        break;

    case ST_update_bootloader:
        update_continue();
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

static void IRQ_INDEX_changed(void)
{
    unsigned int cnt = tim_rdata->cnt;
    time_t now = time_now(), prev = index.isr_time;

    /* Clear INDEX-changed flag. */
    exti->pr = m(pin_index);

    index.isr_time = now;
    if (time_diff(prev, now) < time_us(50))
        return;

    index.count++;
    index.rdata_cnt = cnt;
}

static void index_timer(void *unused)
{
    time_t now = time_now();
    IRQ_global_disable();
    /* index.isr_time mustn't get so old that the time_diff() test in
     * IRQ_INDEX_changed() overflows. To prevent this, we ensure that,
     * at all times,
     *   time_diff(index.isr_time, time_now()) < 2*INDEX_TIMER_PERIOD + delta,
     * where delta is small. */
    if (time_diff(index.isr_time, now) > INDEX_TIMER_PERIOD)
        index.isr_time = now - INDEX_TIMER_PERIOD;
    IRQ_global_enable();
    timer_set(&index.timer, now + INDEX_TIMER_PERIOD);
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
