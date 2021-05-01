/*
 * at32f415/board.c
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

static void mcu_board_init(void)
{
    gpio_pull_up_pins(gpioa, 0x0101); /* PA0,8 */
    gpio_pull_up_pins(gpiob, 0x1803); /* PB0-1,11-12 */
    gpio_pull_up_pins(gpioc, 0xffff); /* PC0-15 */

    /* Flippy TRK0_DISABLE output: Set inactive (LOW). */
    gpio_configure_pin(gpiob, 14, GPO_pushpull(IOSPD_LOW, LOW));

    /* /RDY input line is externally pulled up. */
    gpio_configure_pin(gpiob, 15, GPI_floating);

    /* Single static config. */
    board_config = &_board_config;
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
