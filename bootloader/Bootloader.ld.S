
#if STM32F == 1

#define FLASH_BASE 0x08000000
#define FLASH_LEN  8K

#elif STM32F == 7

#define FLASH_BASE 0x08000000
#define FLASH_LEN  16K

#endif

#include "../scripts/stm32.ld.S"
