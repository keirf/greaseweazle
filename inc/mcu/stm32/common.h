/*
 * stm32/common.h
 * 
 * Core and peripheral registers.
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

/* C pointer types */
#define STK volatile struct stk * const
#define SCB volatile struct scb * const
#define NVIC volatile struct nvic * const
#define DBG volatile struct dbg * const
#define FLASH volatile struct flash * const
#define PWR volatile struct pwr * const
#define RCC volatile struct rcc * const
#define IWDG volatile struct iwdg * const
#define GPIO volatile struct gpio * const
#define EXTI volatile struct exti * const
#define DMA volatile struct dma * const
#define TIM volatile struct tim * const
#define SPI volatile struct spi * const
#define I2C volatile struct i2c * const
#define USART volatile struct usart * const
#define SER_ID volatile uint32_t * const

/* NVIC table */
extern uint32_t vector_table[];

/* System */
void stm32_init(void);
void stm32_bootloader_enter(void);
void system_reset(void);

/* Clocks */
#define SYSCLK     (SYSCLK_MHZ * 1000000)
#define sysclk_ns(x) (((x) * SYSCLK_MHZ) / 1000)
#define sysclk_us(x) ((x) * SYSCLK_MHZ)
#define sysclk_ms(x) ((x) * SYSCLK_MHZ * 1000)
#define sysclk_stk(x) ((x) * (SYSCLK_MHZ / STK_MHZ))

/* SysTick Timer */
#define STK_MHZ    (SYSCLK_MHZ / 8)
void delay_ticks(unsigned int ticks);
void delay_ns(unsigned int ns);
void delay_us(unsigned int us);
void delay_ms(unsigned int ms);

typedef uint32_t stk_time_t;
#define stk_now() (stk->val)
#define stk_diff(x,y) (((x)-(y)) & STK_MASK) /* d = y - x */
#define stk_add(x,d)  (((x)-(d)) & STK_MASK) /* y = x + d */
#define stk_sub(x,d)  (((x)+(d)) & STK_MASK) /* y = x - d */
#define stk_timesince(x) stk_diff(x,stk_now())

#define stk_us(x) ((x) * STK_MHZ)
#define stk_ms(x) stk_us((x) * 1000)
#define stk_sysclk(x) ((x) / (SYSCLK_MHZ / STK_MHZ))

/* NVIC */
#define IRQx_enable(x) do {                     \
    barrier();                                  \
    nvic->iser[(x)>>5] = 1u<<((x)&31);          \
} while (0)
#define IRQx_disable(x) do {                    \
    nvic->icer[(x)>>5] = 1u<<((x)&31);          \
    cpu_sync();                                 \
} while (0)
#define IRQx_is_enabled(x) ((nvic->iser[(x)>>5]>>((x)&31))&1)
#define IRQx_set_pending(x) (nvic->ispr[(x)>>5] = 1u<<((x)&31))
#define IRQx_clear_pending(x) (nvic->icpr[(x)>>5] = 1u<<((x)&31))
#define IRQx_is_pending(x) ((nvic->ispr[(x)>>5]>>((x)&31))&1)
#define IRQx_set_prio(x,y) (nvic->ipr[x] = (y) << 4)
#define IRQx_get_prio(x) (nvic->ipr[x] >> 4)

/* GPIO */
struct gpio;
void gpio_configure_pin(GPIO gpio, unsigned int pin, unsigned int mode);
#define gpio_write_pin(gpio, pin, level) \
    ((gpio)->bsrr = ((level) ? 0x1u : 0x10000u) << (pin))
#define gpio_write_pins(gpio, mask, level) \
    ((gpio)->bsrr = (uint32_t)(mask) << ((level) ? 0 : 16))
#define gpio_read_pin(gpio, pin) (((gpio)->idr >> (pin)) & 1)
bool_t gpio_pins_connected(GPIO gpio1, unsigned int pin1,
                           GPIO gpio2, unsigned int pin2);

/* FPEC */
void fpec_init(void);
void fpec_page_erase(uint32_t flash_address);
void fpec_write(const void *data, unsigned int size, uint32_t flash_address);

/* Pin mappings */
enum { _A = 0, _B, _C, _D, _E, _F, _G, _H, _I };
enum { _OD = 0, _PP };
struct pin_mapping {
    uint8_t pin_id;
    uint8_t gpio_bank;
    uint8_t gpio_pin;
    bool_t  push_pull;
};
GPIO gpio_from_id(uint8_t id);
uint8_t write_mapped_pin(
    const struct pin_mapping *map, int pin_id, bool_t level);
uint8_t read_mapped_pin(
    const struct pin_mapping *map, int pin_id, bool_t *p_level);

/*
 * Local variables:
 * mode: C
 * c-file-style: "Linux"
 * c-basic-offset: 4
 * tab-width: 4
 * indent-tabs-mode: nil
 * End:
 */
