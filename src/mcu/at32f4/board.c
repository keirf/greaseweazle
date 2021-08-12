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

/* V4 pin assignments */

const static struct core_floppy_pins _core_floppy_pins_v4 = {
    .trk0   = 4, /* PB4 */
    .wrprot = 3, /* PB3 */
    .dir    = 8, /* PB8 */
    .step   = 6, /* PB6 */
    .wgate  = 7, /* PB7 */
    .head   = 5  /* PB5 */
};

const static struct pin_mapping _msel_pins_v4[] = {
    { 10, _A,  3 },
    { 12, _B,  9 },
    { 14, _A,  4 },
    { 16, _A,  1 },
    {  0,  0,  0 }
};

const static struct pin_mapping _user_pins_v4[] = {
    {  2, _A,  6 },
    {  4, _A,  5 },
    {  6, _A,  7 },
    {  0,  0,  0 }
};

/* V4 Slim pin assignments */

const static struct core_floppy_pins _core_floppy_pins_v4_slim = {
    .trk0   = 7, /* PB7 */
    .wrprot = 8, /* PB8 */
    .dir    = 5, /* PB5 */
    .step   = 6, /* PB6 */
    .wgate  = 3, /* PB3 */
    .head   = 9  /* PB9 */
};

const static struct pin_mapping _msel_pins_v4_slim[] = {
    { 10, _B,  4 },
    { 14, _B,  1 },
    {  0,  0,  0 }
};

const static struct pin_mapping _user_pins_v4_slim[] = {
    {  0,  0,  0 }
};

const static struct board_config _board_config[] = {
    [F4SM_v4] = {
        .hse_mhz   = 8,
        .flippy    = TRUE,
        .user_pins = _user_pins_v4,
        .msel_pins = _msel_pins_v4 },
    [F4SM_v4_slim] = {
        .hse_mhz   = 16,
        .hse_byp   = TRUE,
        .user_pins = _user_pins_v4_slim,
        .msel_pins = _msel_pins_v4_slim },
};

const struct core_floppy_pins *core_floppy_pins;

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
    if (id >= ARRAY_SIZE(_board_config))
        early_fatal(2);

    /* Single static config. */
    gw_info.hw_submodel = id;
    board_config = &_board_config[id];
}

static void mcu_board_init(void)
{
    switch (gw_info.hw_submodel) {
    case F4SM_v4:
        gpio_pull_up_pins(gpioa, 0x0101); /* PA0,8 */
        gpio_pull_up_pins(gpiob, 0x1803); /* PB0-1,11-12 */
        gpio_pull_up_pins(gpioc, 0xffff); /* PC0-15 */
        core_floppy_pins = &_core_floppy_pins_v4;
        break;

    case F4SM_v4_slim:
        gpio_pull_up_pins(gpioa, 0x01fb); /* PA0-1,3-8 */
        gpio_pull_up_pins(gpiob, 0x0800); /* PB11 */
        gpio_pull_up_pins(gpioc, 0xffff); /* PC0-15 */
        core_floppy_pins = &_core_floppy_pins_v4_slim;
        break;
    }

    /* Flippy TRK0_DISABLE output: Set inactive (LOW). */
    if (board_config->flippy)
        gpio_configure_pin(gpiob, 14, GPO_pushpull(IOSPD_LOW, LOW));
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
