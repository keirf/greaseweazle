/*
 * testmode.c
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

#define CMD_option_bytes 0
#define CMD_pins         1
#define CMD_led          2

struct cmd {
    uint32_t cmd;
    union {
        uint8_t pins[64/8];
        uint32_t x[28/4];
    } u;
};

struct rsp {
    union {
        uint8_t opt[32];
        uint8_t pins[64/8];
        uint32_t x[32/4];
    } u;
};

#define TEST_BIT(p,n) (!!((p)[(n)/8] & (1<<((n)&7))))
#define SET_BIT(p,n) ((p)[(n)/8] |= (1<<((n)&7)))

extern struct pin_mapping testmode_in_pins[];
extern struct pin_mapping testmode_out_pins[];
void testmode_get_option_bytes(void *buf);

static void testmode_set_pin(unsigned int pin, bool_t level)
{
    int rc;
    rc = write_mapped_pin(testmode_out_pins, pin, level);
    if (rc != ACK_OKAY)
        rc = write_mapped_pin(board_config->msel_pins, pin, level);
    if (rc != ACK_OKAY)
        rc = write_mapped_pin(board_config->user_pins, pin, level);
}

static bool_t testmode_get_pin(unsigned int pin)
{
    bool_t level;
    int rc = read_mapped_pin(testmode_in_pins, pin, &level);
    if (rc != ACK_OKAY)
        level = FALSE;
    return level;
}

static void set_pins(uint8_t *pins)
{
    int i;
    bool_t level;

    for (i = 0; i <= 34; i++) {
        level = TEST_BIT(pins, i);
        testmode_set_pin(i, level);
    }
}

static void get_pins(uint8_t *pins)
{
    int i;
    bool_t level;

    for (i = 0; i <= 34; i++) {
        level = testmode_get_pin(i);
        if (level)
            SET_BIT(pins, i);
    }
}

void testmode_process(void)
{
    int len = ep_rx_ready(EP_RX);
    struct cmd cmd;
    struct rsp rsp;

    if (len < 0)
        return;

    len = min_t(int, len, 32);
    usb_read(EP_RX, &cmd, len);
    if (len < 32)
        return;

    memset(&rsp, 0, 32);

    switch (cmd.cmd) {
    case CMD_option_bytes: {
        testmode_get_option_bytes(rsp.u.opt);
        break;
    }
    case CMD_pins: {
        set_pins(cmd.u.pins);
        get_pins(rsp.u.pins);
        break;
    }
    case CMD_led: {
        act_led(!!cmd.u.pins[0]);
        break;
    }
    }

    usb_write(EP_TX, &rsp, 32);
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
