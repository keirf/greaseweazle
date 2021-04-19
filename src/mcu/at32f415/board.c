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
    gpio_pull_up_pins(gpioa, 0xe1fe); /* PA1-8,13-15 */
    gpio_pull_up_pins(gpiob, 0x0027); /* PB0-2,5 */
    gpio_pull_up_pins(gpioc, 0xffff); /* PC0-15 */
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
