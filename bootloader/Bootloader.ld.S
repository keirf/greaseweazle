
#if MCU == STM32F1

#define FLASH_BASE 0x08000000
#define FLASH_LEN  8K

#elif MCU == STM32F7 || MCU == AT32F4

#define FLASH_BASE 0x08000000
#define FLASH_LEN  16K

#endif

#include "../scripts/stm32.ld.S"
