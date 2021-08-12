/*
 * at32f4xx/testmode.c
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

const struct pin_mapping testmode_in_pins[] = {
    {  8, _B, 10 },
    { 26, _B,  4 },
    { 28, _B,  3 },
    { 30, _A, 15 },
    { 34, _B, 15 },
    {  0,  0,  0 }
};

const struct pin_mapping testmode_out_pins[] = {
    { 18, _B,  8 },
    { 20, _B,  6 },
    { 22, _A,  2 },
    { 24, _B,  7 },
    { 32, _B,  5 },
    { 33, _B, 14 },
    {  0,  0,  0 }
};

void testmode_get_option_bytes(void *buf)
{
    memcpy(buf, (void *)0x1ffff800, 32);
}

#define gpio_wdata  gpioa
#define pin_wdata   2
#define tim_wdata   (tim2)
#define GPO_bus GPO_pushpull(IOSPD_LOW,HIGH)
#define AFO_bus AFO_pushpull(IOSPD_LOW)
void testmode_wdat_osc_on(void)
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
void testmode_wdat_osc_off(void)
{
    gpio_configure_pin(gpio_wdata, pin_wdata, GPO_bus);
    tim_wdata->ccer = 0;
    tim_wdata->cr1 = 0;
    tim_wdata->sr = 0;
}

uint8_t testmode_init(void)
{
    switch (gw_info.hw_submodel) {
    case F4SM_v4:
        return ACK_OKAY;
    }
    return ACK_BAD_COMMAND;
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
