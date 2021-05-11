/*
 * testmode.c
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

#include "testmode.h"

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

static unsigned int testmode_test_headers(void)
{
    int i, rc = TESTHEADER_success;
    bool_t keep_pa9_high = FALSE;

#ifndef NDEBUG
    return rc;
#endif

#if MCU == AT32F4
    if (at32f4_series == AT32F415) {
        /* AT32F415: PA9 LOW trips OTG VbusBSen and drops the USB connection. 
         * See Datasheet Table 5 Footnote 8. */
        keep_pa9_high = TRUE;
    }
#endif

    /* Can RXI and TXO pull themselves up and down? */
    for (i = keep_pa9_high ? 1 : 0; i < 2; i++) {
        gpio_configure_pin(gpioa, 9+i, GPI_pull_down);
        delay_ms(1);
        rc++;
        if (gpio_read_pin(gpioa, 9+i) != LOW)
            goto out;
        gpio_configure_pin(gpioa, 9+i, GPI_pull_up);
        delay_ms(1);
        rc++;
        if (gpio_read_pin(gpioa, 9+i) != HIGH)
            goto out;
    }

    /* Are RXI and TXO shorted? */
    for (i = keep_pa9_high ? 1 : 0; i < 2; i++) {
        gpio_configure_pin(gpioa, 9+i, GPO_pushpull(IOSPD_LOW, LOW));
        delay_ms(1);
        rc++;
        if (gpio_read_pin(gpioa, 10-i) != HIGH)
            goto out;
        gpio_configure_pin(gpioa, 9+i, GPI_pull_up);
    }

    rc = TESTHEADER_success;

out:
    for (i = 0; i < 2; i++)
        gpio_configure_pin(gpioa, 9+i, GPI_pull_up);
    return rc;
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
    case CMD_test_headers: {
        rsp.u.x[0] = testmode_test_headers();
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
