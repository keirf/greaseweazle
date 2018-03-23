/*
 * gotek/board.c
 * 
 * Gotek board-specific setup and management.
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

uint8_t board_id;

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
    uint16_t pa_skip, pb_skip;

    /* PA0-7 (floppy outputs), PA9-10 (serial console), PA11-12 (USB) */
    pa_skip = 0x1eff;

    /* PB0 (USB disconnect), PB4,6,8,13 (floppy inputs). */
    pb_skip = 0x2151;

    /* Pull up all PCx pins. */
    gpio_pull_up_pins(gpioc, ~0x0000);

    /* Wait for ID to stabilise at PC[15:12]. */
    delay_us(5);
    board_id = (gpioc->idr >> 12) & 0xf;

    gpio_pull_up_pins(gpioa, ~pa_skip);
    gpio_pull_up_pins(gpiob, ~pb_skip);
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
