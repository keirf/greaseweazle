
#include "../stm32/f1_regs.h"

#define RCC_CFGR_PLLRANGE_GT72MHZ (1u<<31)
#define RCC_CFGR_PLLMUL_18 ((uint32_t)0x20040000)
#define RCC_CFGR_USBPSC_3  ((uint32_t)0x08400000)
#define RCC_CFGR_HSE_PREDIV2 (1u<<17)
#define RCC_CFGR_APB2PSC_2 (4u<<11)
#define RCC_CFGR_APB1PSC_2 (4u<< 8)

#define RCC_PLL (&rcc->cfgr2)
#define RCC_PLL_PLLCFGEN  (1u<<31)
#define RCC_PLL_FREF_MASK (7u<<24)
#define RCC_PLL_FREF_8M   (2u<<24)

static volatile uint32_t * const RCC_MISC2 = (uint32_t *)(RCC_BASE + 0x54);
#define RCC_MISC2_AUTOSTEP_EN (3u<< 4)

#define TIM_CR1_PMEN (1u<<10)
