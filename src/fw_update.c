/*
 * fw_update.c
 * 
 * Update bootloader for main firmware.
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

/* Main bootloader: flashes the main firmware (last 96kB of Flash). */
#define FIRMWARE_START 0x08002000
#define FIRMWARE_END   0x08010000

int EXC_reset(void) __attribute__((alias("main")));

static void canary_init(void)
{
    _irq_stackbottom[0] = _thread_stackbottom[0] = 0xdeadbeef;
}

static void canary_check(void)
{
    ASSERT(_irq_stackbottom[0] == 0xdeadbeef);
    ASSERT(_thread_stackbottom[0] == 0xdeadbeef);
}

static void erase_old_firmware(void)
{
    uint32_t p;
    for (p = FIRMWARE_START; p < FIRMWARE_END; p += FLASH_PAGE_SIZE)
        fpec_page_erase(p);
}

static enum {
    ST_inactive,
    ST_command_wait,
    ST_update,
} state = ST_inactive;

static uint8_t u_buf[256];
static uint32_t u_prod;

static struct gw_info gw_info = {
    /* Max Revs == 0 signals that this is the Bootloader. */
    .max_rev = 0,
    /* Only support two commands: GET_INFO and UPDATE. */
    .max_cmd = CMD_UPDATE,
};

static void update_reset(void)
{
    state = ST_inactive;
}

static void update_configure(void)
{
    state = ST_command_wait;
    u_prod = 0;
}

const struct usb_class_ops usb_cdc_acm_ops = {
    .reset = update_reset,
    .configure = update_configure
};

static void end_command(void *ack, unsigned int ack_len)
{
    usb_write(EP_TX, ack, ack_len);
    u_prod = 0;
}

static struct {
    uint32_t len;
    uint32_t cur;
} update;

static void update_prep(uint32_t len)
{
    fpec_init();
    erase_old_firmware();

    state = ST_update;
    memset(&update, 0, sizeof(update));
    update.len = len;

    printk("Update: %u bytes\n", len);
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
        fpec_write(u_buf, nr, FIRMWARE_START + update.cur);
        update.cur += nr;
        u_prod -= nr;
        memcpy(u_buf, &u_buf[nr], u_prod);
    }

    if (update.cur >= update.len) {
        uint16_t crc = crc16_ccitt((void *)FIRMWARE_START, update.len, 0xffff);
        printk("Final CRC: %04x (%s)\n", crc, crc ? "FAIL" : "OK");
        u_buf[0] = !!crc;
        state = ST_command_wait;
        end_command(u_buf, 1);
    }
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
        gw_info.fw_major = fw_major;
        gw_info.fw_minor = fw_minor;
        /* sample_freq is used as flags: bit 0 indicates if we entered 
         * the bootloader because PA14 is strapped to GND. */
        gw_info.sample_freq = !gpio_read_pin(gpioa, 14);
        memcpy(&u_buf[2], &gw_info, sizeof(gw_info));
        resp_sz += 32;
        break;
    }
    case CMD_UPDATE: {
        uint32_t u_len = *(uint32_t *)&u_buf[2];
        if (len != 6) goto bad_command;
        if (u_len & 3) goto bad_command;
        update_prep(u_len);
        break;
    }
    default:
        goto bad_command;
    }

    u_buf[1] = ACK_OKAY;
out:
    end_command(u_buf, resp_sz);
    return;

bad_command:
    u_buf[1] = ACK_BAD_COMMAND;
    goto out;
}

static void update_process(void)
{
    int len;

    switch (state) {

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

    case ST_update:
        update_continue();
        break;

    default:
        break;

    }
}

int main(void)
{
    /* Relocate DATA. Initialise BSS. */
    if (_sdat != _ldat)
        memcpy(_sdat, _ldat, _edat-_sdat);
    memset(_sbss, 0, _ebss-_sbss);

    /* Turn off serial-wire JTAG and reclaim the GPIOs. */
    afio->mapr = AFIO_MAPR_SWJ_CFG_DISABLED;

    /* Enable GPIOA, set all pins as floating, except PA14 = weak pull-up. */
    rcc->apb2enr = RCC_APB2ENR_IOPAEN;
    gpioa->odr = 0xffffu;
    gpioa->crh = 0x48444444u;
    gpioc->crl = 0x44444444u;

    /* Enter update mode only if PA14 (DCLK) is strapped to GND. */
    if (gpio_read_pin(gpioa, 14)) {
        /* Nope, so jump straight at the main firmware. */
        uint32_t sp = *(uint32_t *)FIRMWARE_START;
        uint32_t pc = *(uint32_t *)(FIRMWARE_START + 4);
        if (sp != ~0u) { /* only if firmware is apparently not erased */
            asm volatile (
                "mov sp,%0 ; blx %1"
                :: "r" (sp), "r" (pc));
        }
    }

    canary_init();
    stm32_init();
    console_init();
    console_crash_on_input();
    board_init();
    delay_ms(200); /* 5v settle */

    printk("\n** Greaseweazle Update Bootloader v%u.%u\n", fw_major, fw_minor);
    printk("** Keir Fraser <keir.xen@gmail.com>\n");
    printk("** https://github.com/keirf/Greaseweazle\n\n");

    gpio_configure_pin(gpioa, 14, GPI_pull_up);

    usb_init();

    for (;;) {
        canary_check();
        usb_process();
        update_process();
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
