/*
 * stm32/common_regs.h
 * 
 * Core and peripheral register definitions.
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

/* SysTick timer */
struct stk {
    uint32_t ctrl;     /* 00: Control and status */
    uint32_t load;     /* 04: Reload value */
    uint32_t val;      /* 08: Current value */
    uint32_t calib;    /* 0C: Calibration value */
};

#define STK_CTRL_COUNTFLAG  (1u<<16)
#define STK_CTRL_CLKSOURCE  (1u<< 2)
#define STK_CTRL_TICKINT    (1u<< 1)
#define STK_CTRL_ENABLE     (1u<< 0)

#define STK_MASK            ((1u<<24)-1)

#define STK_BASE 0xe000e010

/* System control block */
struct scb {
    uint32_t cpuid;    /* 00: CPUID base */
    uint32_t icsr;     /* 04: Interrupt control and state */
    uint32_t vtor;     /* 08: Vector table offset */
    uint32_t aircr;    /* 0C: Application interrupt and reset control */
    uint32_t scr;      /* 10: System control */
    uint32_t ccr;      /* 14: Configuration and control */
    uint32_t shpr1;    /* 18: System handler priority reg #1 */
    uint32_t shpr2;    /* 1C: system handler priority reg #2 */
    uint32_t shpr3;    /* 20: System handler priority reg #3 */
    uint32_t shcsr;    /* 24: System handler control and state */
    uint32_t cfsr;     /* 28: Configurable fault status */
    uint32_t hfsr;     /* 2C: Hard fault status */
    uint32_t _unused;  /* 30: - */
    uint32_t mmar;     /* 34: Memory management fault address */
    uint32_t bfar;     /* 38: Bus fault address */
};

#define SCB_CCR_BP             (1u<<18)
#define SCB_CCR_IC             (1u<<17)
#define SCB_CCR_DC             (1u<<16)
#define SCB_CCR_STKALIGN       (1u<< 9)
#define SCB_CCR_BFHFNMIGN      (1u<< 8)
#define SCB_CCR_DIV_0_TRP      (1u<< 4)
#define SCB_CCR_UNALIGN_TRP    (1u<< 3)
#define SCB_CCR_USERSETMPEND   (1u<< 1)
#define SCB_CCR_NONBASETHRDENA (1u<< 0)

#define SCB_SHCSR_USGFAULTENA    (1u<<18)
#define SCB_SHCSR_BUSFAULTENA    (1u<<17)
#define SCB_SHCSR_MEMFAULTENA    (1u<<16)
#define SCB_SHCSR_SVCALLPENDED   (1u<<15)
#define SCB_SHCSR_BUSFAULTPENDED (1u<<14)
#define SCB_SHCSR_MEMFAULTPENDED (1u<<13)
#define SCB_SHCSR_USGFAULTPENDED (1u<<12)
#define SCB_SHCSR_SYSTICKACT     (1u<<11)
#define SCB_SHCSR_PENDSVACT      (1u<<10)
#define SCB_SHCSR_MONITORACT     (1u<< 8)
#define SCB_SHCSR_SVCALLACT      (1u<< 7)
#define SCB_SHCSR_USGFAULTACT    (1u<< 3)
#define SCB_SHCSR_BUSFAULTACT    (1u<< 1)
#define SCB_SHCSR_MEMFAULTACT    (1u<< 0)

#define SCB_CFSR_DIVBYZERO     (1u<<25)
#define SCB_CFSR_UNALIGNED     (1u<<24)
#define SCB_CFSR_NOCP          (1u<<19)
#define SCB_CFSR_INVPC         (1u<<18)
#define SCB_CFSR_INVSTATE      (1u<<17)
#define SCB_CFSR_UNDEFINSTR    (1u<<16)
#define SCB_CFSR_BFARVALID     (1u<<15)
#define SCB_CFSR_STKERR        (1u<<12)
#define SCB_CFSR_UNSTKERR      (1u<<11)
#define SCB_CFSR_IMPRECISERR   (1u<<10)
#define SCB_CFSR_PRECISERR     (1u<< 9)
#define SCB_CFSR_IBUSERR       (1u<< 8)
#define SCB_CFSR_MMARVALID     (1u<< 7)
#define SCB_CFSR_MSTKERR       (1u<< 4)
#define SCB_CFSR_MUNSTKERR     (1u<< 3)
#define SCB_CFSR_DACCVIOL      (1u<< 1)
#define SCB_CFSR_IACCVIOL      (1u<< 0)

#define SCB_AIRCR_VECTKEY     (0x05fau<<16)
#define SCB_AIRCR_SYSRESETREQ (1u<<2)

#define SCB_BASE 0xe000ed00

/* Nested vectored interrupt controller */
struct nvic {
    uint32_t iser[32]; /*  00: Interrupt set-enable */
    uint32_t icer[32]; /*  80: Interrupt clear-enable */
    uint32_t ispr[32]; /* 100: Interrupt set-pending */
    uint32_t icpr[32]; /* 180: Interrupt clear-pending */
    uint32_t iabr[64]; /* 200: Interrupt active */
    uint8_t ipr[80];   /* 300: Interrupt priority */
};

#define NVIC_BASE 0xe000e100

/* Independent Watchdog */
struct iwdg {
    uint32_t kr;   /* 00: Key */
    uint32_t pr;   /* 04: Prescaler */
    uint32_t rlr;  /* 08: Reload */
    uint32_t sr;   /* 0C: Status */
};

#define IWDG_BASE 0x40003000

struct exti {
    uint32_t imr;        /* 00: Interrupt mask */
    uint32_t emr;        /* 04: Event mask */
    uint32_t rtsr;       /* 08: Rising trigger selection */
    uint32_t ftsr;       /* 0C: Falling trigger selection */
    uint32_t swier;      /* 10: Software interrupt event */
    uint32_t pr;         /* 14: Pending */
};

/* Timer */
struct tim {
    uint32_t cr1;   /* 00: Control 1 */
    uint32_t cr2;   /* 04: Control 2 */
    uint32_t smcr;  /* 08: Slave mode control */
    uint32_t dier;  /* 0C: DMA/interrupt enable */
    uint32_t sr;    /* 10: Status */
    uint32_t egr;   /* 14: Event generation */
    uint32_t ccmr1; /* 18: Capture/compare mode 1 */
    uint32_t ccmr2; /* 1C: Capture/compare mode 2 */
    uint32_t ccer;  /* 20: Capture/compare enable */
    uint32_t cnt;   /* 24: Counter */
    uint32_t psc;   /* 28: Prescaler */
    uint32_t arr;   /* 2C: Auto-reload */
    uint32_t rcr;   /* 30: Repetition counter */
    uint32_t ccr1;  /* 34: Capture/compare 1 */
    uint32_t ccr2;  /* 38: Capture/compare 2 */
    uint32_t ccr3;  /* 3C: Capture/compare 3 */
    uint32_t ccr4;  /* 40: Capture/compare 4 */
    uint32_t bdtr;  /* 44: Break and dead-time */
    uint32_t dcr;   /* 48: DMA control */
    uint32_t dmar;  /* 4C: DMA address for full transfer */
    uint32_t _pad;  /* 50: - */
    uint32_t ccmr3; /* 54: Capture/compare mode 3 */
    uint32_t ccr5;  /* 58: Capture/compare 5 */
    uint32_t ccr6;  /* 5C: Capture/compare 6 */
};

#define TIM_CR1_ARPE         (1u<<7)
#define TIM_CR1_DIR          (1u<<4)
#define TIM_CR1_OPM          (1u<<3)
#define TIM_CR1_URS          (1u<<2)
#define TIM_CR1_UDIS         (1u<<1)
#define TIM_CR1_CEN          (1u<<0)

#define TIM_CR2_TI1S         (1u<<7)
#define TIM_CR2_MMS(x)       ((x)<<4)
#define TIM_CR2_CCDS         (1u<<3)

#define TIM_SMCR_ETP         (1u<<15)
#define TIM_SMCR_ETC         (1u<<14)
#define TIM_SMCR_ETPS(x)     ((x)<<12)
#define TIM_SMCR_ETF(x)      ((x)<<8)
#define TIM_SMCR_MSM         (1u<<7)
#define TIM_SMCR_TS(x)       ((x)<<4)
#define TIM_SMCR_SMS(x)      ((x)<<0)

#define TIM_DIER_TDE         (1u<<14)
#define TIM_DIER_CC4DE       (1u<<12)
#define TIM_DIER_CC3DE       (1u<<11)
#define TIM_DIER_CC2DE       (1u<<10)
#define TIM_DIER_CC1DE       (1u<<9)
#define TIM_DIER_UDE         (1u<<8)
#define TIM_DIER_TIE         (1u<<6)
#define TIM_DIER_CC4IE       (1u<<4)
#define TIM_DIER_CC3IE       (1u<<3)
#define TIM_DIER_CC2IE       (1u<<2)
#define TIM_DIER_CC1IE       (1u<<1)
#define TIM_DIER_UIE         (1u<<0)

#define TIM_SR_CC4OF         (1u<<12)
#define TIM_SR_CC3OF         (1u<<11)
#define TIM_SR_CC2OF         (1u<<10)
#define TIM_SR_CC1OF         (1u<<9)
#define TIM_SR_TIF           (1u<<6)
#define TIM_SR_CC4IF         (1u<<4)
#define TIM_SR_CC3IF         (1u<<3)
#define TIM_SR_CC2IF         (1u<<2)
#define TIM_SR_CC1IF         (1u<<1)
#define TIM_SR_UIF           (1u<<0)

#define TIM_EGR_TG           (1u<<6)
#define TIM_EGR_CC4G         (1u<<4)
#define TIM_EGR_CC3G         (1u<<3)
#define TIM_EGR_CC2G         (1u<<2)
#define TIM_EGR_CC1G         (1u<<1)
#define TIM_EGR_UG           (1u<<0)

#define TIM_CCMR1_OC2CE      (1u <<15)
#define TIM_CCMR1_OC2M(x)    ((x)<<12)
#define TIM_CCMR1_OC2PE      (1u <<11)
#define TIM_CCMR1_OC2FE      (1u <<10)
#define TIM_CCMR1_CC2S(x)    ((x)<< 8)
#define TIM_CCMR1_OC1CE      (1u << 7)
#define TIM_CCMR1_OC1M(x)    ((x)<< 4)
#define TIM_CCMR1_OC1PE      (1u << 3)
#define TIM_CCMR1_OC1FE      (1u << 2)
#define TIM_CCMR1_CC1S(x)    ((x)<< 0)

#define TIM_CCMR1_IC2F(x)    ((x)<<12)
#define TIM_CCMR1_IC2PSC(x)  ((x)<<10)
#define TIM_CCMR1_IC1F(x)    ((x)<< 4)
#define TIM_CCMR1_IC1PSC(x)  ((x)<< 2)

#define TIM_CCMR2_OC4CE      (1u <<15)
#define TIM_CCMR2_OC4M(x)    ((x)<<12)
#define TIM_CCMR2_OC4PE      (1u <<11)
#define TIM_CCMR2_OC4FE      (1u <<10)
#define TIM_CCMR2_CC4S(x)    ((x)<< 8)
#define TIM_CCMR2_OC3CE      (1u << 7)
#define TIM_CCMR2_OC3M(x)    ((x)<< 4)
#define TIM_CCMR2_OC3PE      (1u << 3)
#define TIM_CCMR2_OC3FE      (1u << 2)
#define TIM_CCMR2_CC3S(x)    ((x)<< 0)

#define TIM_CCMR2_IC4F(x)    ((x)<<12)
#define TIM_CCMR2_IC4PSC(x)  ((x)<<10)
#define TIM_CCMR2_IC3F(x)    ((x)<< 4)
#define TIM_CCMR2_IC3PSC(x)  ((x)<< 2)

#define TIM_OCM_FROZEN       (0u)
#define TIM_OCM_SET_HIGH     (1u)
#define TIM_OCM_SET_LOW      (2u)
#define TIM_OCM_TOGGLE       (3u)
#define TIM_OCM_FORCE_LOW    (4u)
#define TIM_OCM_FORCE_HIGH   (5u)
#define TIM_OCM_PWM1         (6u)
#define TIM_OCM_PWM2         (7u)
#define TIM_OCM_MASK         (7u)

#define TIM_CCS_OUTPUT       (0u)
#define TIM_CCS_INPUT_TI1    (1u)
#define TIM_CCS_INPUT_TI2    (2u)
#define TIM_CCS_INPUT_TRC    (3u)
#define TIM_CCS_MASK         (3u)

#define TIM_CCER_CC4P        (1u<<13)
#define TIM_CCER_CC4E        (1u<<12)
#define TIM_CCER_CC3P        (1u<< 9)
#define TIM_CCER_CC3E        (1u<< 8)
#define TIM_CCER_CC2P        (1u<< 5)
#define TIM_CCER_CC2E        (1u<< 4)
#define TIM_CCER_CC1P        (1u<< 1)
#define TIM_CCER_CC1E        (1u<< 0)

#define TIM_BDTR_MOE         (1u<<15)
#define TIM_BDTR_AOE         (1u<<14)
#define TIM_BDTR_BKP         (1u<<13)
#define TIM_BDTR_BKE         (1u<<12)
#define TIM_BDTR_OSSR        (1u<<11)
#define TIM_BDTR_OSSI        (1u<<10)
#define TIM_BDTR_LOCK(x)     ((x)<<8)
#define TIM_BDTR_DTG(x)      ((x)<<0)

/* SPI/I2S */
struct spi {
    uint32_t cr1;     /* 00: Control 1 */
    uint32_t cr2;     /* 04: Control 2 */
    uint32_t sr;      /* 08: Status */
    uint32_t dr;      /* 0C: Data */
    uint32_t crcpr;   /* 10: CRC polynomial */
    uint32_t rxcrcr;  /* 14: RX CRC */
    uint32_t txcrcr;  /* 18: TX CRC */
    uint32_t i2scfgr; /* 1C: I2S configuration */
    uint32_t i2spr;   /* 20: I2S prescaler */
};

#define SPI_CR1_BIDIMODE  (1u<<15)
#define SPI_CR1_BIDIOE    (1u<<14)
#define SPI_CR1_CRCEN     (1u<<13)
#define SPI_CR1_CRCNEXT   (1u<<12)
#define SPI_CR1_DFF       (1u<<11)
#define SPI_CR1_RXONLY    (1u<<10)
#define SPI_CR1_SSM       (1u<< 9)
#define SPI_CR1_SSI       (1u<< 8)
#define SPI_CR1_LSBFIRST  (1u<< 7)
#define SPI_CR1_SPE       (1u<< 6)
#define SPI_CR1_BR_DIV2   (0u<< 3)
#define SPI_CR1_BR_DIV4   (1u<< 3)
#define SPI_CR1_BR_DIV8   (2u<< 3)
#define SPI_CR1_BR_DIV16  (3u<< 3)
#define SPI_CR1_BR_DIV32  (4u<< 3)
#define SPI_CR1_BR_DIV64  (5u<< 3)
#define SPI_CR1_BR_DIV128 (6u<< 3)
#define SPI_CR1_BR_DIV256 (7u<< 3)
#define SPI_CR1_BR_MASK   (7u<< 3)
#define SPI_CR1_MSTR      (1u<< 2)
#define SPI_CR1_CPOL      (1u<< 1)
#define SPI_CR1_CPHA      (1u<< 0)

#define SPI_CR2_TXEIE     (1u<< 7)
#define SPI_CR2_RXNEIE    (1u<< 6)
#define SPI_CR2_ERRIE     (1u<< 5)
#define SPI_CR2_SSOE      (1u<< 2)
#define SPI_CR2_TXDMAEN   (1u<< 1)
#define SPI_CR2_RXDMAEN   (1u<< 0)

#define SPI_SR_BSY        (1u<< 7)
#define SPI_SR_OVR        (1u<< 6)
#define SPI_SR_MODF       (1u<< 5)
#define SPI_SR_CRCERR     (1u<< 4)
#define SPI_SR_USR        (1u<< 3)
#define SPI_SR_CHSIDE     (1u<< 2)
#define SPI_SR_TXE        (1u<< 1)
#define SPI_SR_RXNE       (1u<< 0)

#define SPI1_BASE 0x40013000
#define SPI2_BASE 0x40003800
#define SPI3_BASE 0x40003C00

/*
 * Local variables:
 * mode: C
 * c-file-style: "Linux"
 * c-basic-offset: 4
 * tab-width: 4
 * indent-tabs-mode: nil
 * End:
 */
