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

static void mcu_board_init(void)
{
    gpio_pull_up_pins(gpioa, 0x0101); /* PA0,8 */
    gpio_pull_up_pins(gpiob, 0xdc03); /* PB0-1,10-12,14-15 */
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
