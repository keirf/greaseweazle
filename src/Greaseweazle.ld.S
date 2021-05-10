
#if MCU == STM32F1

#define FLASH_BASE 0x08002000
#define FLASH_LEN  56K

#elif MCU == STM32F7 || MCU == AT32F4

#define FLASH_BASE 0x08004000
#define FLASH_LEN  48K

#endif

#include "../scripts/stm32.ld.S"
