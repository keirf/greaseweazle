/*
 * f7/board.c
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
    uint16_t a = 0x9930; /* PA4-5,8,11-12,15 */
    uint16_t b = 0x23f8; /* PB3-9,13 */
    uint16_t c = 0xffe7; /* PC0-2,5-15 */
    uint16_t d = 0xffff; /* PD0-15 */
    uint16_t e = 0xffff; /* PE0-15 */
    uint16_t f = 0xffff; /* PF0-15 */
    uint16_t g = 0xffff; /* PG0-15 */
    uint16_t h = 0xffff; /* PH0-15 */
    uint16_t i = 0xffff; /* PI0-15 */
    uint32_t ahb1enr = rcc->ahb1enr;

    switch (gw_info.hw_submodel) {
    case F7SM_basic:
        break;
    case F7SM_ambertronic_f7_plus:
        break;
    case F7SM_lightning:
        /* Uses PE12 and PE13 for extra drive outputs. */
        ahb1enr |= RCC_AHB1ENR_GPIOEEN;
        break;
    }

    /* Enable all GPIO bank register clocks to configure unused pins. */
    rcc->ahb1enr |= (RCC_AHB1ENR_GPIOAEN |
                     RCC_AHB1ENR_GPIOBEN |
                     RCC_AHB1ENR_GPIOCEN |
                     RCC_AHB1ENR_GPIODEN |
                     RCC_AHB1ENR_GPIOEEN |
                     RCC_AHB1ENR_GPIOFEN |
                     RCC_AHB1ENR_GPIOGEN |
                     RCC_AHB1ENR_GPIOHEN |
                     RCC_AHB1ENR_GPIOIEN);
    peripheral_clock_delay();

    gpio_pull_up_pins(gpioa, a);
    gpio_pull_up_pins(gpiob, b);
    gpio_pull_up_pins(gpioc, c);
    gpio_pull_up_pins(gpiod, d);
    gpio_pull_up_pins(gpioe, e);
    gpio_pull_up_pins(gpiof, f);
    gpio_pull_up_pins(gpiog, g);
    gpio_pull_up_pins(gpioh, h);
    gpio_pull_up_pins(gpioi, i);

    /* Unused GPIO banks can have their clocks disabled again. They will 
     * statically hold their configuration state. */
    peripheral_clock_delay();
    rcc->ahb1enr = ahb1enr;
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
