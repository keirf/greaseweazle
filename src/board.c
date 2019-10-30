/*
 * board.c
 * 
 * Board-specific setup and management.
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

/* Pull up currently unused and possibly-floating pins. */
static void gpio_pull_up_pins(GPIO gpio, uint16_t mask)
{
    unsigned int i;
    for (i = 0; i < 16; i++) {
        if (mask & 1)
            gpio_configure_pin(gpio, i, GPI_pull_up);
        mask >>= 1;
    }
}

void board_init(void)
{
    /* Pull up all unused pins. */
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
