/*
 * at32f4/board.c
 * 
 * Board-specific setup and management.
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

#define gpio_led gpiob
#define pin_led 13

const static struct pin_mapping _msel_pins[] = {
    { 10, _A,  3 },
    { 12, _B,  9 },
    { 14, _A,  4 },
    { 16, _A,  1 },
    {  0,  0,  0 }
};

const static struct pin_mapping _user_pins[] = {
    {  2, _A,  6 },
    {  4, _A,  5 },
    {  6, _A,  7 },
    {  0,  0,  0 }
};

const static struct board_config _board_config = {
    .flippy    = TRUE,
    .user_pins = _user_pins,
    .msel_pins = _msel_pins
};

/* Blink the activity LED to indicate fatal error. */
void early_fatal(int blinks)
{
    int i;
    rcc->apb2enr |= RCC_APB2ENR_IOPBEN;
    delay_ticks(10);
    gpio_configure_pin(gpio_led, pin_led, GPO_pushpull(IOSPD_LOW, HIGH));
    for (;;) {
        for (i = 0; i < blinks; i++) {
            gpio_write_pin(gpiob, 13, LOW);
            early_delay_ms(150);
            gpio_write_pin(gpiob, 13, HIGH);
            early_delay_ms(150);
        }
        early_delay_ms(2000);
    }
}

void identify_board_config(void)
{
    uint16_t low, high;
    uint8_t id = 0;
    int i;

    rcc->apb2enr |= RCC_APB2ENR_IOPCEN;
    early_delay_us(2);

    /* Pull PC[15:13] low, and check which are tied HIGH. */
    for (i = 0; i < 3; i++)
        gpio_configure_pin(gpioc, 13+i, GPI_pull_down);
    early_delay_us(10);
    high = (gpioc->idr >> 13) & 7;

    /* Pull PC[15:13] high, and check which are tied LOW. */
    for (i = 0; i < 3; i++)
        gpio_configure_pin(gpioc, 13+i, GPI_pull_up);
    early_delay_us(10);
    low = (~gpioc->idr >> 13) & 7;

    /* Each PCx pin defines a 'trit': 0=float, 1=low, 2=high. 
     * We build a 3^3 ID space from the resulting three-trit ID. */
    for (i = 0; i < 3; i++) {
        id *= 3;
        switch ((high>>1&2) | (low>>2&1)) {
        case 0: break;          /* float = 0 */
        case 1: id += 1; break; /* LOW   = 1 */
        case 2: id += 2; break; /* HIGH  = 2 */
        case 3: early_fatal(1); /* cannot be tied HIGH *and* LOW! */
        }
        high <<= 1;
        low <<= 1;
    }

    /* Panic if the ID is unrecognised. */
    if (id != 0)
        early_fatal(2);

    /* Single static config. */
    gw_info.hw_submodel = id;
    board_config = &_board_config;
}

static void mcu_board_init(void)
{
    gpio_pull_up_pins(gpioa, 0x0101); /* PA0,8 */
    gpio_pull_up_pins(gpiob, 0x1803); /* PB0-1,11-12 */
    gpio_pull_up_pins(gpioc, 0xffff); /* PC0-15 */

    /* Flippy TRK0_DISABLE output: Set inactive (LOW). */
    gpio_configure_pin(gpiob, 14, GPO_pushpull(IOSPD_LOW, LOW));

    /* /RDY input line is externally pulled up. */
    gpio_configure_pin(gpiob, 15, GPI_floating);
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
