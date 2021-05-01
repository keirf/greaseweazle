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

const struct board_config *board_config;

GPIO gpio_from_id(uint8_t id)
{
    switch (id) {
    case _A: return gpioa;
    case _B: return gpiob;
    case _C: return gpioc;
    case _D: return gpiod;
    case _E: return gpioe;
    case _F: return gpiof;
    case _G: return gpiog;
#if MCU == STM32F7
    case _H: return gpioh;
    case _I: return gpioi;
#endif
    }
    ASSERT(0);
    return NULL;
}

uint8_t write_mapped_pin(
    const struct pin_mapping *map, int pin_id, bool_t level)
{
    const struct pin_mapping *pin;

    for (pin = map; pin->pin_id != 0; pin++)
        if (pin->pin_id == pin_id)
            goto found;

    return ACK_BAD_PIN;

found:
    gpio_write_pin(gpio_from_id(pin->gpio_bank), pin->gpio_pin, level);
    return ACK_OKAY;
}

uint8_t read_mapped_pin(
    const struct pin_mapping *map, int pin_id, bool_t *p_level)
{
    const struct pin_mapping *pin;

    for (pin = map; pin->pin_id != 0; pin++)
        if (pin->pin_id == pin_id)
            goto found;

    return ACK_BAD_PIN;

found:
    *p_level = gpio_read_pin(gpio_from_id(pin->gpio_bank), pin->gpio_pin);
    return ACK_OKAY;
}

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

#if MCU == STM32F1
#include "mcu/stm32f1/board.c"
#elif MCU == STM32F7
#include "mcu/stm32f7/board.c"
#elif MCU == AT32F415
#include "mcu/at32f415/board.c"
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
