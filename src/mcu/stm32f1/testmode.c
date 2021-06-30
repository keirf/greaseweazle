/*
 * f1/testmode.c
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

const struct pin_mapping testmode_in_pins[] = {
    {  8, _B,  6 },
    { 26, _B,  7 },
    { 28, _B,  8 },
    { 30, _B,  3 },
    { 34, _A,  8 },
    {  0,  0,  0 }
};

const struct pin_mapping testmode_out_pins[] = {
    { 18, _B, 12 },
    { 20, _B, 13 },
    { 22, _B,  4 },
    { 24, _B, 14 },
    { 32, _B, 15 },
    { 33, _A,  2 },
    {  0,  0,  0 }
};

void testmode_get_option_bytes(void *buf)
{
    memset(buf, 0, 32);
    memcpy(buf, (void *)0x1ffff800, 16);
}

#define gpio_wdata  gpiob
#define pin_wdata   4
#define tim_wdata   (tim3)
void testmode_wdat_osc_on(void)
{
    tim_wdata->psc = SYSCLK_MHZ/TIME_MHZ-1;
    tim_wdata->ccmr1 = (TIM_CCMR1_CC1S(TIM_CCS_OUTPUT) |
                        TIM_CCMR1_OC1M(TIM_OCM_PWM1));
    tim_wdata->ccer = TIM_CCER_CC1E;
    tim_wdata->ccr1 = time_us(1);
    tim_wdata->arr = time_us(2)-1;
    tim_wdata->dier = TIM_DIER_UDE;
    tim_wdata->cr2 = 0;
    tim_wdata->egr = TIM_EGR_UG;
    tim_wdata->sr = 0;
    tim_wdata->cr1 = TIM_CR1_CEN;
    gpio_wdata->crl = gpio_wdata->crl | (8 << (pin_wdata<<2)); /* AFO */
}
void testmode_wdat_osc_off(void)
{
    gpio_wdata->crl = gpio_wdata->crl & ~(8 << (pin_wdata<<2)); /* GPO */
    tim_wdata->ccer = 0;
    tim_wdata->cr1 = 0;
    tim_wdata->sr = 0;
}

uint8_t testmode_init(void)
{
    switch (gw_info.hw_submodel) {
    case F1SM_plus:
    case F1SM_plus_unbuffered:
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
