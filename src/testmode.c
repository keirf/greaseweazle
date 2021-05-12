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

/* It so happens that all supported boards use the same pin and timer for 
 * WDAT, so we can share the code here. Future boards may require this to 
 * be made board-specific. */
#define gpio_wdata  gpioa
#define pin_wdata   2
#define tim_wdata   (tim2)
#define GPO_bus GPO_pushpull(IOSPD_LOW,HIGH)
#define AFO_bus AFO_pushpull(IOSPD_LOW)
static void testmode_wdat_osc_on(void)
{
    tim_wdata->psc = SYSCLK_MHZ/TIME_MHZ-1;
    tim_wdata->ccmr2 = (TIM_CCMR2_CC3S(TIM_CCS_OUTPUT) |
                        TIM_CCMR2_OC3M(TIM_OCM_PWM1));
    tim_wdata->ccer = TIM_CCER_CC3E;
    tim_wdata->ccr3 = time_us(1);
    tim_wdata->arr = time_us(2)-1;
    tim_wdata->dier = TIM_DIER_UDE;
    tim_wdata->cr2 = 0;
    tim_wdata->egr = TIM_EGR_UG;
    tim_wdata->sr = 0;
    tim_wdata->cr1 = TIM_CR1_CEN;
    gpio_configure_pin(gpio_wdata, pin_wdata, AFO_bus);
}
static void testmode_wdat_osc_off(void)
{
    gpio_configure_pin(gpio_wdata, pin_wdata, GPO_bus);
    tim_wdata->ccer = 0;
    tim_wdata->cr1 = 0;
    tim_wdata->sr = 0;
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
    case CMD_wdat_osc_on: {
        testmode_wdat_osc_on();
        break;
    }
    case CMD_wdat_osc_off: {
        testmode_wdat_osc_off();
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
