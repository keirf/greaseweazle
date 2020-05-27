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

#if STM32F == 1
#define gpio_led gpioc
#define pin_led 13
#elif STM32F == 7
#define gpio_led gpiob
#define pin_led 13
#endif

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

#if STM32F == 1

static void mcu_board_init(void)
{
    gpio_pull_up_pins(gpioa, 0xe1fe); /* PA1-8,13-15 */
    gpio_pull_up_pins(gpiob, 0x0027); /* PB0-2,5 */
    gpio_pull_up_pins(gpioc, 0xffff); /* PC0-15 */
}

#elif STM32F == 7

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

#endif

void board_init(void)
{
    mcu_board_init();

#ifdef NDEBUG
    /* Pull up unused debug pins (A9,A10 = serial console). */
    gpio_pull_up_pins(gpioa, (1u<<9) | (1u<<10));
#endif

    /* Activity LED is active low. */
    gpio_configure_pin(gpio_led, pin_led, GPO_pushpull(IOSPD_LOW, HIGH));
}

/* Set the activity LED status. */
void act_led(bool_t on)
{
    gpio_write_pin(gpio_led, pin_led, on ? LOW : HIGH);
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
