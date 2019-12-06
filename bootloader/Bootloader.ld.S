
#if STM32F == 1

#define FLASH_BASE 0x08000000
#define FLASH_LEN  8K
#define RAM_BASE   0x20000000
#define RAM_LEN    20K

#elif STM32F == 7

#define FLASH_BASE 0x08000000
#define FLASH_LEN  16K
#define RAM_BASE   0x20000000
#define RAM_LEN    64K

#endif

#include "../scripts/stm32.ld.S"
