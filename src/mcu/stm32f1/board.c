/*
 * f1/board.c
 * 
 * Board-specific setup and management.
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

#define gpio_led gpioc
#define pin_led 13

const static struct pin_mapping _msel_pins_std[] = {
    { 10, _B, 11 },
    { 14, _B, 10 },
    {  0,  0,  0 }
};

const static struct pin_mapping _msel_pins_f1_plus[] = {
    { 10, _B, 11 },
    { 12, _B,  0 },
    { 14, _B, 10 },
    { 16, _B,  1 },
    {  0,  0,  0 }
};

const static struct pin_mapping _user_pins_std[] = {
    { 2, _B,  9, _OD },
    { 0,  0,  0, _OD } };
const static struct pin_mapping _user_pins_f1_plus[] = {
    { 2, _B,  9, _PP },
    { 4, _A,  3, _PP },
    { 6, _A,  1, _PP },
    { 0,  0,  0, _PP } };
const static struct pin_mapping _user_pins_f1_plus_unbuffered[] = {
    { 2, _B,  9, _OD },
    { 4, _A,  3, _OD },
    { 6, _A,  1, _OD },
    { 0,  0,  0, _OD } };

const static struct board_config _board_config[] = {
    [F1SM_basic] = {
        .flippy    = FALSE,
        .user_pins = _user_pins_std,
        .msel_pins = _msel_pins_std },
    [F1SM_plus] = {
        .flippy    = TRUE,
        .user_pins = _user_pins_f1_plus,
        .msel_pins = _msel_pins_f1_plus },
    [F1SM_plus_unbuffered] = {
        .flippy    = TRUE,
        .user_pins = _user_pins_f1_plus_unbuffered,
        .msel_pins = _msel_pins_f1_plus }
};

/* Blink the activity LED to indicate fatal error. */
static void blink_fatal(int blinks)
{
    int i;
    gpio_configure_pin(gpio_led, pin_led, GPO_pushpull(IOSPD_LOW, HIGH));
    for (;;) {
        for (i = 0; i < blinks; i++) {
            gpio_write_pin(gpio_led, pin_led, LOW);
            delay_ms(150);
            gpio_write_pin(gpio_led, pin_led, HIGH);
            delay_ms(150);
        }
        delay_ms(2000);
    }
}

static void identify_board_config(void)
{
    uint16_t low, high;
    uint8_t id = 0;
    int i;

    /* Pull PC[15:14] low, and check which are tied HIGH. */
    for (i = 0; i < 2; i++)
        gpio_configure_pin(gpioc, 14+i, GPI_pull_down);
    delay_us(10);
    high = (gpioc->idr >> 14) & 3;

    /* Pull PC[15:14] high, and check which are tied LOW. */
    for (i = 0; i < 2; i++)
        gpio_configure_pin(gpioc, 14+i, GPI_pull_up);
    delay_us(10);
    low = (~gpioc->idr >> 14) & 3;

    /* Each PCx pin defines a 'trit': 0=float, 1=low, 2=high. 
     * We build a 2^3 ID space from the resulting two-trit ID. */
    for (i = 0; i < 2; i++) {
        id *= 3;
        switch ((high&2) | (low>>1&1)) {
        case 0: break;          /* float = 0 */
        case 1: id += 1; break; /* LOW   = 1 */
        case 2: id += 2; break; /* HIGH  = 2 */
        case 3: blink_fatal(1); /* cannot be tied HIGH *and* LOW! */
        }
        high <<= 1;
        low <<= 1;
    }

    /* Panic if the ID is unrecognised. */
    if (id >= ARRAY_SIZE(_board_config))
        blink_fatal(2);

    gw_info.hw_submodel = id;
    board_config = &_board_config[id];
}

static void mcu_board_init(void)
{
    uint16_t pu[] = {
        [_A] = 0xe1fe, /* PA1-8,13-15 */
        [_B] = 0x0e27, /* PB0-2,5,9-11 */
        [_C] = 0xffff, /* PC0-15 */
    };
    const struct pin_mapping *mpin;
    const struct pin_mapping *upin;

    identify_board_config();

    /* MSEL pins: do not default these pins to pull-up mode. */
    for (mpin = board_config->msel_pins; mpin->pin_id != 0; mpin++)
        pu[mpin->gpio_bank] &= ~(1u << mpin->gpio_pin);

    /* User pins: do not default these pins to pull-up mode. */
    for (upin = board_config->user_pins; upin->pin_id != 0; upin++)
        pu[upin->gpio_bank] &= ~(1u << upin->gpio_pin);

    /* Flippy TRK0_DISABLE output: Set inactive (LOW). */
    if (board_config->flippy) {
        gpio_configure_pin(gpioa, 2, GPO_pushpull(IOSPD_LOW, LOW));
        pu[_A] &= ~(1u << 2); /* PA2 */
    }

    switch (gw_info.hw_submodel) {
    case F1SM_plus:
    case F1SM_plus_unbuffered:
        /* /RDY input line is externally pulled up. */
        pu[_A] &= ~(1u << 8); /* PA8 */
        break;
    }

    gpio_pull_up_pins(gpioa, pu[_A]);
    gpio_pull_up_pins(gpiob, pu[_B]);
    gpio_pull_up_pins(gpioc, pu[_C]);
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
