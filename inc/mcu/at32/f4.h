
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

#undef SYSCLK_MHZ
#define SYSCLK_MHZ 144
#define AHB_MHZ (SYSCLK_MHZ / 1)  /* 144MHz */
#define APB1_MHZ (SYSCLK_MHZ / 2) /* 72MHz */
#define APB2_MHZ (SYSCLK_MHZ / 2) /* 72MHz */

enum {
    F4SM_v4 = 0,
    F4SM_v4_slim,
};

/* Core floppy pin assignments vary between F4 submodels (except INDEX, RDATA, 
 * and WDATA). All the following assignments are within GPIOB. */
struct core_floppy_pins {
    uint8_t trk0;
    uint8_t wrprot;
    uint8_t dir;
    uint8_t step;
    uint8_t wgate;
    uint8_t head;
};
extern const struct core_floppy_pins *core_floppy_pins;
