/*
 * stm32/f7.h
 * 
 * Core and peripheral registers.
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

/* C pointer types */
#define CACHE volatile struct cache * const
#define SYSCFG volatile struct syscfg * const
#define DMA_STR volatile struct dma_str * const
#define HSPHYC volatile struct hsphyc * const

/* C-accessible registers. */
static STK stk = (struct stk *)STK_BASE;
static SCB scb = (struct scb *)SCB_BASE;
static NVIC nvic = (struct nvic *)NVIC_BASE;
static DBG dbg = (struct dbg *)DBG_BASE;
static CACHE cache = (struct cache *)CACHE_BASE;
static FLASH flash = (struct flash *)FLASH_BASE;
static PWR pwr = (struct pwr *)PWR_BASE;
static RCC rcc = (struct rcc *)RCC_BASE;
static IWDG iwdg = (struct iwdg *)IWDG_BASE;
static GPIO gpioa = (struct gpio *)GPIOA_BASE;
static GPIO gpiob = (struct gpio *)GPIOB_BASE;
static GPIO gpioc = (struct gpio *)GPIOC_BASE;
static GPIO gpiod = (struct gpio *)GPIOD_BASE;
static GPIO gpioe = (struct gpio *)GPIOE_BASE;
static GPIO gpiof = (struct gpio *)GPIOF_BASE;
static GPIO gpiog = (struct gpio *)GPIOG_BASE;
static GPIO gpioh = (struct gpio *)GPIOH_BASE;
static GPIO gpioi = (struct gpio *)GPIOI_BASE;
static SYSCFG syscfg = (struct syscfg *)SYSCFG_BASE;
static EXTI exti = (struct exti *)EXTI_BASE;
static DMA dma1 = (struct dma *)DMA1_BASE;
static DMA dma2 = (struct dma *)DMA2_BASE;
static TIM tim1 = (struct tim *)TIM1_BASE;
static TIM tim2 = (struct tim *)TIM2_BASE;
static TIM tim3 = (struct tim *)TIM3_BASE;
static TIM tim4 = (struct tim *)TIM4_BASE;
static TIM tim5 = (struct tim *)TIM5_BASE;
static TIM tim6 = (struct tim *)TIM6_BASE;
static TIM tim7 = (struct tim *)TIM7_BASE;
static TIM tim8 = (struct tim *)TIM8_BASE;
static TIM tim9 = (struct tim *)TIM9_BASE;
static TIM tim10 = (struct tim *)TIM10_BASE;
static TIM tim11 = (struct tim *)TIM11_BASE;
static TIM tim12 = (struct tim *)TIM12_BASE;
static TIM tim13 = (struct tim *)TIM13_BASE;
static TIM tim14 = (struct tim *)TIM14_BASE;
static SPI spi1 = (struct spi *)SPI1_BASE;
static SPI spi2 = (struct spi *)SPI2_BASE;
static SPI spi3 = (struct spi *)SPI3_BASE;
static SPI spi4 = (struct spi *)SPI4_BASE;
static SPI spi5 = (struct spi *)SPI5_BASE;
static I2C i2c1 = (struct i2c *)I2C1_BASE;
static I2C i2c2 = (struct i2c *)I2C2_BASE;
static I2C i2c3 = (struct i2c *)I2C3_BASE;
static USART usart1 = (struct usart *)USART1_BASE;
static USART usart2 = (struct usart *)USART2_BASE;
static USART usart3 = (struct usart *)USART3_BASE;
static USART usart4 = (struct usart *)USART4_BASE;
static USART usart5 = (struct usart *)USART5_BASE;
static USART usart6 = (struct usart *)USART6_BASE;
static HSPHYC hsphyc = (struct hsphyc *)HSPHYC_BASE;
static SER_ID ser_id = (uint32_t *)0x1ff07a10;

#define SYSCLK_MHZ 216
#define AHB_MHZ (SYSCLK_MHZ / 1)  /* 216MHz */
#define APB1_MHZ (SYSCLK_MHZ / 4) /* 54MHz */
#define APB2_MHZ (SYSCLK_MHZ / 2) /* 108MHz */

#define FLASH_PAGE_SIZE 16384

/* Delay after enabling peripheral clock, before accessing peripheral 
 * (Ref STMicro RM0431, Section 5.2.12) */
void peripheral_clock_delay(void);

void gpio_set_af(GPIO gpio, unsigned int pin, unsigned int af);

/*
 * Local variables:
 * mode: C
 * c-file-style: "Linux"
 * c-basic-offset: 4
 * tab-width: 4
 * indent-tabs-mode: nil
 * End:
 */
