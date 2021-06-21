
#include "../stm32/f1_regs.h"

#define RCC_CFGR_PLLRANGE_GT72MHZ (1u<<31)
#define RCC_CFGR_PLLMUL_18 ((uint32_t)0x20040000)
#define RCC_CFGR_USBPSC_3  ((uint32_t)0x08400000)
#define RCC_CFGR_APB2PSC_2 (4u<<11)
#define RCC_CFGR_APB1PSC_2 (4u<< 8)

#define TIM_CR1_PMEN (1u<<10)
