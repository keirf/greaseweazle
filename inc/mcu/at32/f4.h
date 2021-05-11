
#include "../stm32/f1.h"

#undef FLASH_PAGE_SIZE
extern unsigned int FLASH_PAGE_SIZE;

#define AT32F403  0x02
#define AT32F413  0x04
#define AT32F415  0x05
#define AT32F403A 0x07
#define AT32F407  0x08
extern unsigned int at32f4_series;

void identify_board_config(void);

/* On reset, SYSCLK=HSI at 8MHz. SYSCLK runs at 1MHz. */
void early_fatal(int blinks) __attribute__((noreturn));
#define early_delay_ms(ms) (delay_ticks((ms)*1000))
#define early_delay_us(us) (delay_ticks((us)*1))
