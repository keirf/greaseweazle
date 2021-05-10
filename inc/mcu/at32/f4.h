
#include "../stm32/f1.h"

#undef FLASH_PAGE_SIZE
extern unsigned int FLASH_PAGE_SIZE;

#define AT32F403  0x02
#define AT32F413  0x04
#define AT32F415  0x05
#define AT32F403A 0x07
#define AT32F407  0x08
extern unsigned int at32f4_series;
