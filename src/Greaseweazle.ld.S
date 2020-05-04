
#if STM32F == 1

#define FLASH_BASE 0x08002000
#define FLASH_LEN  56K

#elif STM32F == 7

#define FLASH_BASE 0x08004000
#define FLASH_LEN  48K

#endif

#include "../scripts/stm32.ld.S"
