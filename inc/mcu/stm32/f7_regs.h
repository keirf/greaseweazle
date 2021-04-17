/*
 * stm32/f7_regs.h
 * 
 * Core and peripheral register definitions.
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

struct dbg {
    uint32_t mcu_idcode; /* 00: MCU ID code */
    uint32_t mcu_cr;     /* 04: Debug MCU configuration */
    uint32_t mcu_apb1_fz;/* 08: Debug MCU APB1 freeze */
    uint32_t mcu_apb2_fz;/* 0C: Debug MCU APB2 freeze */
};

#define DBG_BASE 0xe0042000

struct cpufeat {
    uint32_t clidr;      /* 00: Cache level ID */
    uint32_t ctr;        /* 04: Cache type */
    uint32_t ccsidr;     /* 08: Cache size ID */
    uint32_t csselr;     /* 10: Cache size selection */
};

#define CCSIDR_SETS(x) (((x)>>13)&0x7fffu)
#define CCSIDR_WAYS(x) (((x)>> 3)& 0x3ffu)

#define CPUFEAT_BASE 0xe000ed78

struct cache {
    uint32_t iciallu;    /* 00: ICache invalidate all to PoU */
    uint32_t _unused0;
    uint32_t icimvau;    /* 08: ICache invalidate by address to PoU */
    uint32_t dcimvac;    /* 0C: DCache invalidate by address to PoC */
    uint32_t dcisw;      /* 10: DCache invalidate by set/way */
    uint32_t dccmvau;    /* 14: DCache clean by adress to PoU */
    uint32_t dccmvac;    /* 18: DCache clean by address to PoC */
    uint32_t dccsw;      /* 1C: DCache clean by set/way */
    uint32_t dccimvac;   /* 20: DCache clean & invalidate by address to PoC */
    uint32_t dccisw;     /* 24: DCache clean & invalidate by set/way */
    uint32_t bpiall;
};

#define DCISW_WAY(x)  ((x)<<30)
#define DCISW_SET(x)  ((x)<< 5)

#define CACHE_BASE 0xe000ef50    

/* Flash memory interface */
struct flash {
    uint32_t acr;      /* 00: Flash access control */
    uint32_t keyr;     /* 04: Flash key */
    uint32_t optkeyr;  /* 08: Flash option key */
    uint32_t sr;       /* 0C: Flash status */
    uint32_t cr;       /* 10: Flash control */
    uint32_t optcr;    /* 14: Flash option control */
    uint32_t optcr1;   /* 18: Flash option control */
    uint32_t optcr2;   /* 1C: Flash option control */
};

#define FLASH_ACR_ARTRST     (1u<<11)
#define FLASH_ACR_ARTEN      (1u<< 9)
#define FLASH_ACR_PRFTEN     (1u<< 8)
#define FLASH_ACR_LATENCY(w) ((w)<<0) /* wait states */

#define FLASH_SR_BSY         (1u<<16)
#define FLASH_SR_RDERR       (1u<< 8)
#define FLASH_SR_ERRSERR     (1u<< 7)
#define FLASH_SR_PGPERR      (1u<< 6)
#define FLASH_SR_PGAERR      (1u<< 5)
#define FLASH_SR_WRPERR      (1u<< 4)
#define FLASH_SR_OPERR       (1u<< 1)
#define FLASH_SR_EOP         (1u<< 0)

#define FLASH_CR_LOCK        (1u<<31)
#define FLASH_CR_RDERRIE     (1u<<26)
#define FLASH_CR_ERRIE       (1u<<25)
#define FLASH_CR_EOPIE       (1u<<24)
#define FLASH_CR_STRT        (1u<<16)
#define FLASH_CR_PSIZE(x)    ((x)<<8)
#define FLASH_CR_SNB(x)      ((x)<<3)
#define FLASH_CR_MER         (1u<< 2)
#define FLASH_CR_SER         (1u<< 1)
#define FLASH_CR_PG          (1u<< 0)

#define FLASH_BASE 0x40023c00

/* Power control */
struct pwr {
    uint32_t cr1;      /* 00: Power control #1 */
    uint32_t csr1;     /* 04: Power control/status #1 */
    uint32_t cr2;      /* 08: Power control #2 */
    uint32_t csr2;     /* 0C: Power control/status #2 */
};

#define PWR_CR1_UDEN(x)      ((x)<<18)
#define PWR_CR1_ODSWEN       (1u<<17)
#define PWR_CR1_ODEN         (1u<<16)
#define PWR_CR1_VOS(x)       ((x)<<14)
#define PWR_CR1_ADCDC1       (1u<<13)
#define PWR_CR1_MRUDS        (1u<<11)
#define PWR_CR1_LPUDS        (1u<<10)
#define PWR_CR1_FPDS         (1u<< 9)
#define PWR_CR1_DBP          (1u<< 8)
#define PWR_CR1_PLS(x)       ((x)<<5)
#define PWR_CR1_PVDE         (1u<< 4)
#define PWR_CR1_CSBF         (1u<< 3)
#define PWR_CR1_PDDS         (1u<< 1)
#define PWR_CR1_LPDS         (1u<< 0)

#define PWR_CSR1_ODSWRDY     (1u<<17)
#define PWR_CSR1_ODRDY       (1u<<16)
#define PWR_CSR1_VOSRDY      (1u<<14)
#define PWR_CSR1_BRE         (1u<< 9)
#define PWR_CSR1_EIWUP       (1u<< 8)
#define PWR_CSR1_BRR         (1u<< 3)
#define PWR_CSR1_PVDO        (1u<< 2)
#define PWR_CSR1_SBF         (1u<< 1)
#define PWR_CSR1_WUIF        (1u<< 0)

#define PWR_BASE 0x40007000

/* Reset and clock control */
struct rcc {
    uint32_t cr;       /* 00: Clock control */
    uint32_t pllcfgr;  /* 04: PLL configuration */
    uint32_t cfgr;     /* 08: Clock configuration */
    uint32_t cir;      /* 0C: Clock interrupt */
    uint32_t ahb1rstr; /* 10: AHB1 peripheral reset */
    uint32_t ahb2rstr; /* 14: AHB2 peripheral reset */
    uint32_t ahb3rstr; /* 18: AHB3 peripheral reset */
    uint32_t _unused0; /* 1C: - */
    uint32_t apb1rstr; /* 20: APB1 peripheral reset */
    uint32_t apb2rstr; /* 24: APB2 peripheral reset */
    uint32_t _unused1; /* 28: - */
    uint32_t _unused2; /* 2C: - */
    uint32_t ahb1enr;  /* 30: AHB1 peripheral clock enable */
    uint32_t ahb2enr;  /* 34: AHB2 peripheral clock enable */
    uint32_t ahb3enr;  /* 38: AHB3 peripheral clock enable */
    uint32_t _unused3; /* 3C: - */
    uint32_t apb1enr;  /* 40: APB1 peripheral clock enable */
    uint32_t apb2enr;  /* 44: APB1 peripheral clock enable */
    uint32_t _unused4; /* 48: - */
    uint32_t _unused5; /* 4C: - */
    uint32_t ahb1lpenr;/* 50: AHB1 peripheral clock enable (low-power mode) */
    uint32_t ahb2lpenr;/* 54: AHB2 peripheral clock enable (low-power mode) */
    uint32_t ahb3lpenr;/* 58: AHB3 peripheral clock enable (low-power mode) */
    uint32_t _unused6; /* 5C: - */
    uint32_t apb1lpenr;/* 60: APB1 peripheral clock enable (low-power mode) */
    uint32_t apb2lpenr;/* 64: APB2 peripheral clock enable (low-power mode) */
    uint32_t _unused7; /* 68: - */
    uint32_t _unused8; /* 6C: - */
    uint32_t bdcr;     /* 70: Backup domain control */
    uint32_t csr;      /* 74: Clock control & status */
    uint32_t _unused9; /* 78: - */
    uint32_t _unusedA; /* 7C: - */
    uint32_t sscgr;    /* 80: Spread spectrum clock generation */
    uint32_t plli2scfgr; /* 84: PLLI2S configuration */
    uint32_t pllsaicfgr; /* 88: PLLSAI configuration */
    uint32_t dckcfgr1; /* 8C: Dedicated clocks configuration #1 */
    uint32_t dckcfgr2; /* 90: Dedicated clocks configuration #2 */
};

#define RCC_CR_SAIRDY        (1u<<29)
#define RCC_CR_SAION         (1u<<28)
#define RCC_CR_PLLIS2RDY     (1u<<27)
#define RCC_CR_PLLI2SON      (1u<<26)
#define RCC_CR_PLLRDY        (1u<<25)
#define RCC_CR_PLLON         (1u<<24)
#define RCC_CR_CSSON         (1u<<19)
#define RCC_CR_HSEBYP        (1u<<18)
#define RCC_CR_HSERDY        (1u<<17)
#define RCC_CR_HSEON         (1u<<16)
#define RCC_CR_HSIRDY        (1u<<1)
#define RCC_CR_HSION         (1u<<0)

#define RCC_PLLCFGR_PLLQ(x)  ((x)<<24)
#define RCC_PLLCFGR_PLLSRC_HSE (1<<22)
#define RCC_PLLCFGR_PLLP(x)  ((x)<<16)
#define RCC_PLLCFGR_PLLN(x)  ((x)<< 6)
#define RCC_PLLCFGR_PLLM(x)  ((x)<< 0)

#define RCC_CFGR_MCO2(x)     ((x)<<30)
#define RCC_CFGR_MCO2PRE(x)  ((x)<<27)
#define RCC_CFGR_MCO1PRE(x)  ((x)<<24)
#define RCC_CFGR_I2SSCR      (1  <<23)
#define RCC_CFGR_MCO1(x)     ((x)<<21)
#define RCC_CFGR_RTCPRE(x)   ((x)<<16)
#define RCC_CFGR_PPRE2(x)    ((x)<<13)
#define RCC_CFGR_PPRE1(x)    ((x)<<10)
#define RCC_CFGR_HPRE(x)     ((x)<< 4)
#define RCC_CFGR_SWS(x)      ((x)<< 2)
#define RCC_CFGR_SW(x)       ((x)<< 0)

#define RCC_AHB1ENR_OTGHSULPIEN (1u<<30)
#define RCC_AHB1ENR_OTGHSEN  (1u<<29)
#define RCC_AHB1ENR_DMA2EN   (1u<<22)
#define RCC_AHB1ENR_DMA1EN   (1u<<21)
#define RCC_AHB1ENR_DTCMRAMEN (1u<<20)
#define RCC_AHB1ENR_BKPSRAMEN (1u<<18)
#define RCC_AHB1ENR_CRCEN    (1u<<12)
#define RCC_AHB1ENR_GPIOIEN  (1u<< 8)
#define RCC_AHB1ENR_GPIOHEN  (1u<< 7)
#define RCC_AHB1ENR_GPIOGEN  (1u<< 6)
#define RCC_AHB1ENR_GPIOFEN  (1u<< 5)
#define RCC_AHB1ENR_GPIOEEN  (1u<< 4)
#define RCC_AHB1ENR_GPIODEN  (1u<< 3)
#define RCC_AHB1ENR_GPIOCEN  (1u<< 2)
#define RCC_AHB1ENR_GPIOBEN  (1u<< 1)
#define RCC_AHB1ENR_GPIOAEN  (1u<< 0)

#define RCC_AHB2ENR_OTGFSEN  (1u<< 7)
#define RCC_AHB2ENR_RNGEN    (1u<< 6)
#define RCC_AHB2ENR_AESEN    (1u<< 4)

#define RCC_AHB3ENR_QSPIEN   (1u<< 1)
#define RCC_AHB3ENR_FMCEN    (1u<< 0)

#define RCC_APB1ENR_USART8EN (1u<<31)
#define RCC_APB1ENR_USART7EN (1u<<30)
#define RCC_APB1ENR_DACEN    (1u<<29)
#define RCC_APB1ENR_PWREN    (1u<<28)
#define RCC_APB1ENR_CAN1EN   (1u<<25)
#define RCC_APB1ENR_I2C3EN   (1u<<23)
#define RCC_APB1ENR_I2C2EN   (1u<<22)
#define RCC_APB1ENR_I2C1EN   (1u<<21)
#define RCC_APB1ENR_USART5EN (1u<<20)
#define RCC_APB1ENR_USART4EN (1u<<19)
#define RCC_APB1ENR_USART3EN (1u<<18)
#define RCC_APB1ENR_USART2EN (1u<<17)
#define RCC_APB1ENR_SPI3EN   (1u<<15)
#define RCC_APB1ENR_SPI2EN   (1u<<14)
#define RCC_APB1ENR_WWDGEN   (1u<<11)
#define RCC_APB1ENR_RTCAPBEN (1u<<10)
#define RCC_APB1ENR_LPTIM1EN (1u<< 9)
#define RCC_APB1ENR_TIM14EN  (1u<< 8)
#define RCC_APB1ENR_TIM13EN  (1u<< 7)
#define RCC_APB1ENR_TIM12EN  (1u<< 6)
#define RCC_APB1ENR_TIM7EN   (1u<< 5)
#define RCC_APB1ENR_TIM6EN   (1u<< 4)
#define RCC_APB1ENR_TIM5EN   (1u<< 3)
#define RCC_APB1ENR_TIM4EN   (1u<< 2)
#define RCC_APB1ENR_TIM3EN   (1u<< 1)
#define RCC_APB1ENR_TIM2EN   (1u<< 0)

#define RCC_APB2ENR_OTGPHYCEN (1u<<31)
#define RCC_APB2ENR_SAI2EN   (1u<<23)
#define RCC_APB2ENR_SAI1EN   (1u<<22)
#define RCC_APB2ENR_SPI5EN   (1u<<20)
#define RCC_APB2ENR_TIM11EN  (1u<<18)
#define RCC_APB2ENR_TIM10EN  (1u<<17)
#define RCC_APB2ENR_TIM9EN   (1u<<16)
#define RCC_APB2ENR_SYSCFGEN (1u<<14)
#define RCC_APB2ENR_SPI4EN   (1u<<13)
#define RCC_APB2ENR_SPI1EN   (1u<<12)
#define RCC_APB2ENR_SDMMC1EN (1u<<11)
#define RCC_APB2ENR_ADC3EN   (1u<<10)
#define RCC_APB2ENR_ADC2EN   (1u<< 9)
#define RCC_APB2ENR_ADC1EN   (1u<< 8)
#define RCC_APB2ENR_SDMMC2EN (1u<< 7)
#define RCC_APB2ENR_USART6EN (1u<< 5)
#define RCC_APB2ENR_USART1EN (1u<< 4)
#define RCC_APB2ENR_TIM8EN   (1u<< 1)
#define RCC_APB2ENR_TIM1EN   (1u<< 0)

#define RCC_BDCR_BDRST       (1u<<16)
#define RCC_BDCR_RTCEN       (1u<<15)
#define RCC_BDCR_RTCSEL(x)   ((x)<<8)
#define RCC_BDCR_LSEDRV(x)   ((x)<<3)
#define RCC_BDCR_LSEBYP      (1u<< 2)
#define RCC_BDCR_LSERDY      (1u<< 1)
#define RCC_BDCR_LSEON       (1u<< 0)

#define RCC_CSR_LPWRRSTF     (1u<<31)
#define RCC_CSR_WWDGRSTF     (1u<<30)
#define RCC_CSR_IWDGRSTF     (1u<<29)
#define RCC_CSR_SFTRSTF      (1u<<28)
#define RCC_CSR_PORRSTF      (1u<<27)
#define RCC_CSR_PINRSTF      (1u<<26)
#define RCC_CSR_BORRSTF      (1u<<25)
#define RCC_CSR_RMVF         (1u<<24)
#define RCC_CSR_LSIRDY       (1u<< 1)
#define RCC_CSR_LSION        (1u<< 0)

#define RCC_DCKCFGR1_TIMPRE        (1u<<24)
#define RCC_DCKCFGR1_SAI2SEL(x)    ((x)<<22)
#define RCC_DCKCFGR1_SAI1SEL(x)    ((x)<<20)
#define RCC_DCKCFGR1_PLLSAIDIVQ(x) ((x)<< 8)
#define RCC_DCKCFGR1_PLLI2SDIVQ(x) ((x)<< 0)

#define RCC_BASE 0x40023800

/* General-purpose I/O */
struct gpio {
    uint32_t moder;   /* 00: Port mode */
    uint32_t otyper;  /* 04: Port output type */
    uint32_t ospeedr; /* 08: Port output speed */
    uint32_t pupdr;   /* 0C: Port pull-up/pull-down */
    uint32_t idr;     /* 10: Port input data */
    uint32_t odr;     /* 14: Port output data */
    uint32_t bsrr;    /* 18: Port bit set/reset */
    uint32_t lckr;    /* 1C: Port configuration lock */
    uint32_t afrl;    /* 20: Alternate function low */
    uint32_t afrh;    /* 24: Alternate function high */
};

/* 0-1: MODE, 2: OTYPE, 3-4:OSPEED, 5-6:PUPD, 7:OUTPUT_LEVEL */
#define GPI_analog    0x3u
#define GPI(pupd)     (0x0u|((pupd)<<5))
#define PUPD_none     0
#define PUPD_up       1
#define PUPD_down     2
#define GPI_floating  GPI(PUPD_none)
#define GPI_pull_down GPI(PUPD_down)
#define GPI_pull_up   GPI(PUPD_up)

#define GPO_pushpull(speed,level)  (0x1u|((speed)<<3)|((level)<<7))
#define GPO_opendrain(speed,level) (0x5u|((speed)<<3)|((level)<<7))
#define AFI(pupd)                  (0x2u|((pupd)<<5))
#define AFO_pushpull(speed)        (0x2u|((speed)<<3))
#define AFO_opendrain(speed)       (0x6u|((speed)<<3))
#define IOSPD_LOW    0 /*   4MHz @ CL=50pF */
#define IOSPD_MED    1 /*  25MHz @ CL=50pF */
#define IOSPD_HIGH   2 /*  50MHz @ CL=40pF */
#define IOSPD_V_HIGH 3 /* 100MHz @ CL=30pF */
#define LOW  0
#define HIGH 1

#define GPIOA_BASE 0x40020000
#define GPIOB_BASE 0x40020400
#define GPIOC_BASE 0x40020800
#define GPIOD_BASE 0x40020C00
#define GPIOE_BASE 0x40021000
#define GPIOF_BASE 0x40021400
#define GPIOG_BASE 0x40021800
#define GPIOH_BASE 0x40021C00
#define GPIOI_BASE 0x40022000

/* System configuration controller */
struct syscfg {
    uint32_t memrmp;     /* 00: Memory remap */
    uint32_t pmc;        /* 04: Peripheral mode configuration */
    uint32_t exticr1;    /* 08: External interrupt configuration #1 */
    uint32_t exticr2;    /* 0C: External interrupt configuration #2 */
    uint32_t exticr3;    /* 10: External interrupt configuration #3 */
    uint32_t exticr4;    /* 14: External interrupt configuration #4 */
    uint32_t _pad[2];
    uint32_t cmpcr;      /* 20: Compensation cell configuration */
};

#define SYSCFG_BASE 0x40013800

#define EXTI_BASE 0x40013c00

/* DMA */
struct dma_str {
    uint32_t cr;        /* +00: Configuration */
    uint32_t ndtr;      /* +04: Number of data */
    uint32_t par;       /* +08: Peripheral address */
    union {
        uint32_t mar;   /* +0C: Memory address */
        uint32_t m0ar;  /* +0C: Memory 0 address */
    };
    uint32_t m1ar;      /* +10: Memory 1 address */
    uint32_t fcr;       /* +14: FIFO control */
};
struct dma {
    uint32_t lisr;         /* 00: Low interrupt status */
    uint32_t hisr;         /* 00: High interrupt status */
    uint32_t lifcr;        /* 00: Low interrupt flag clear */
    uint32_t hifcr;        /* 00: High interrupt flag clear */
    struct dma_str str[8]; /* 0x10,0x28,..,0xB8: Stream 0,1,..,7 */
};

#define DMA_ISR_TCIF      (1u<<5)
#define DMA_ISR_HTIF      (1u<<4)
#define DMA_ISR_TEIF      (1u<<3)
#define DMA_ISR_DMEIF     (1u<<2)
#define DMA_ISR_FEIF      (1u<<0)

#define DMA_IFCR_CTCIF    (1u<<5)
#define DMA_IFCR_CHTIF    (1u<<4)
#define DMA_IFCR_CTEIF    (1u<<3)
#define DMA_IFCR_CDMEIF   (1u<<2)
#define DMA_IFCR_CFEIF    (1u<<0)

#define DMA_CR_CHSEL(x)   ((x)<<25)
#define DMA_CR_CT         (1u<<19)
#define DMA_CR_DBM        (1u<<18)
#define DMA_CR_PL_LOW     (0u<<16)
#define DMA_CR_PL_MEDIUM  (1u<<16)
#define DMA_CR_PL_HIGH    (2u<<16)
#define DMA_CR_PL_V_HIGH  (3u<<16)
#define DMA_CR_PINCOS     (1u<<15)
#define DMA_CR_MSIZE_8BIT  (0u<<13)
#define DMA_CR_MSIZE_16BIT (1u<<13)
#define DMA_CR_MSIZE_32BIT (2u<<13)
#define DMA_CR_PSIZE_8BIT  (0u<<11)
#define DMA_CR_PSIZE_16BIT (1u<<11)
#define DMA_CR_PSIZE_32BIT (2u<<11)
#define DMA_CR_MINC       (1u<<10)
#define DMA_CR_PINC       (1u<< 9)
#define DMA_CR_CIRC       (1u<< 8)
#define DMA_CR_DIR_M2M    (2u<< 6)
#define DMA_CR_DIR_M2P    (1u<< 6)
#define DMA_CR_DIR_P2M    (0u<< 6)
#define DMA_CR_PFCTRL     (1u<< 5)
#define DMA_CR_TCIE       (1u<< 4)
#define DMA_CR_HTIE       (1u<< 3)
#define DMA_CR_TEIE       (1u<< 2)
#define DMA_CR_DMEIE      (1u<< 1)
#define DMA_CR_EN         (1u<< 0)

#define DMA_FCR_DMDIS     (1u<< 2)

#define DMA1_BASE 0x40026000
#define DMA2_BASE 0x40026400

#define TIM1_BASE 0x40010000
#define TIM2_BASE 0x40000000
#define TIM3_BASE 0x40000400
#define TIM4_BASE 0x40000800
#define TIM5_BASE 0x40000c00
#define TIM6_BASE 0x40001000
#define TIM7_BASE 0x40001400
#define TIM8_BASE 0x40010400
#define TIM9_BASE 0x40014000
#define TIM10_BASE 0x40014400
#define TIM11_BASE 0x40014800
#define TIM12_BASE 0x40001800
#define TIM13_BASE 0x40001c00
#define TIM14_BASE 0x40002000

#define SPI4_BASE 0x40013400
#define SPI5_BASE 0x40015000

/* I2C */
struct i2c {
    uint32_t cr1;      /* 00: Control 1 */
    uint32_t cr2;      /* 04: Control 2 */
    uint32_t oar1;     /* 08: Own address 1 */
    uint32_t oar2;     /* 0C: Own address 2 */
    uint32_t timingr;  /* 10: Timing */
    uint32_t timeoutr; /* 14: Timeout */
    uint32_t isr;      /* 18: Interrupt & status */
    uint32_t icr;      /* 1C: Interrupt clear */
    uint32_t pecr;     /* 20: PEC */
    uint32_t rxdr;     /* 24: Receive data */
    uint32_t txdr;     /* 28: Transmit data */
};

#define I2C_CR1_PECEN     (1u<<23)
#define I2C_CR1_ALERTEN   (1u<<22)
#define I2C_CR1_SMBDEN    (1u<<21)
#define I2C_CR1_SMBHEN    (1u<<20)
#define I2C_CR1_GCEN      (1u<<19)
#define I2C_CR1_NOSTRETCH (1u<<17)
#define I2C_CR1_SBC       (1u<<16)
#define I2C_CR1_RXDMAEN   (1u<<15)
#define I2C_CR1_TXDMAEN   (1u<<14)
#define I2C_CR1_ANFOFF    (1u<<12)
#define I2C_CR1_DNF(x)    ((x)<<8)
#define I2C_CR1_ERRIE     (1u<< 7)
#define I2C_CR1_TCIE      (1u<< 6)
#define I2C_CR1_STOPIE    (1u<< 5)
#define I2C_CR1_NACKIE    (1u<< 4)
#define I2C_CR1_ADDRIE    (1u<< 3)
#define I2C_CR1_RXIE      (1u<< 2)
#define I2C_CR1_TXIE      (1u<< 1)
#define I2C_CR1_PE        (1u<< 0)

#define I2C_CR2_PECBYTE   (1u<<26)
#define I2C_CR2_AUTOEND   (1u<<25)
#define I2C_CR2_RELOAD    (1u<<24)
#define I2C_CR2_NBYTES(x) ((x)<<16)
#define I2C_CR2_NACK      (1u<<15)
#define I2C_CR2_STOP      (1u<<14)
#define I2C_CR2_START     (1u<<13)
#define I2C_CR2_HEAD10R   (1u<<12)
#define I2C_CR2_ADD10     (1u<<11)
#define I2C_CR2_RD_WRN    (1u<<10)
#define I2C_CR2_SADD(x)   ((x)<<0)

#define I2C_OA1_EN        (1u<<15)
#define I2C_OA1_MODE      (1u<<10)

#define I2C_ISR_DIR       (1<<16)
#define I2C_ISR_BUSY      (1<<15)
#define I2C_ISR_ALERT     (1<<13)
#define I2C_ISR_TIMEOUT   (1<<12)
#define I2C_ISR_PECERR    (1<<11)
#define I2C_ISR_OVR       (1<<10)
#define I2C_ISR_ARLO      (1<< 9)
#define I2C_ISR_BERR      (1<< 8)
#define I2C_ISR_TCR       (1<< 7)
#define I2C_ISR_TC        (1<< 6)
#define I2C_ISR_STOPF     (1<< 5)
#define I2C_ISR_NACKF     (1<< 4)
#define I2C_ISR_ADDR      (1<< 3)
#define I2C_ISR_RXNE      (1<< 2)
#define I2C_ISR_TXIS      (1<< 1)
#define I2C_ISR_TXE       (1<< 0)

#define I2C_ICR_ALERTCF   (1<<13)
#define I2C_ICR_TIMOUTCF  (1<<12)
#define I2C_ICR_PECCF     (1<<11)
#define I2C_ICR_OVRCF     (1<<10)
#define I2C_ICR_ARLOCF    (1<< 9)
#define I2C_ICR_BERRCF    (1<< 8)
#define I2C_ICR_STOPCF    (1<< 5)
#define I2C_ICR_NACKCF    (1<< 4)
#define I2C_ICR_ADDRCF    (1<< 3)

#define I2C1_BASE 0x40005400
#define I2C2_BASE 0x40005800
#define I2C3_BASE 0x40005C00

/* USART */
struct usart {
    uint32_t cr1;  /* 00: Control #1 */
    uint32_t cr2;  /* 00: Control #2 */
    uint32_t cr3;  /* 00: Control #3 */
    uint32_t brr;  /* 00: Baud rate */
    uint32_t gtpr; /* 00: Guard time & prescaler */
    uint32_t rtor; /* 00: Receive timeout */
    uint32_t rqr;  /* 00: Request */
    uint32_t isr;  /* 00: Interrupt & status */
    uint32_t icr;  /* 00: Interrupt flag clear */
    uint32_t rdr;  /* 00: Receive data */
    uint32_t tdr;  /* 00: Transmit data */
};

#define USART_CR1_M1         (1u<<28)
#define USART_CR1_OVER8      (1u<<15)
#define USART_CR1_CMIE       (1u<<14)
#define USART_CR1_MME        (1u<<13)
#define USART_CR1_M0         (1u<<12)
#define USART_CR1_WAKE       (1u<<11)
#define USART_CR1_PCE        (1u<<10)
#define USART_CR1_PS         (1u<< 9)
#define USART_CR1_PEIE       (1u<< 8)
#define USART_CR1_TXEIE      (1u<< 7)
#define USART_CR1_TCIE       (1u<< 6)
#define USART_CR1_RXNEIE     (1u<< 5)
#define USART_CR1_IDLEIE     (1u<< 4) 
#define USART_CR1_TE         (1u<< 3)
#define USART_CR1_RE         (1u<< 2)
#define USART_CR1_UE         (1u<< 0)

#define USART_CR3_CTSIE      (1u<<10)
#define USART_CR3_CTSE       (1u<< 9)
#define USART_CR3_RTSE       (1u<< 8)
#define USART_CR3_DMAT       (1u<< 7)
#define USART_CR3_DMAR       (1u<< 6)
#define USART_CR3_SCEN       (1u<< 5)
#define USART_CR3_NACK       (1u<< 4)
#define USART_CR3_HDSEL      (1u<< 3)
#define USART_CR3_IRLP       (1u<< 2)
#define USART_CR3_IREN       (1u<< 1)
#define USART_CR3_EIE        (1u<< 0)

#define USART_RQR_TXFRQ      (1u<< 4)
#define USART_RQR_RXFRQ      (1u<< 3)
#define USART_RQR_MMRQ       (1u<< 2)
#define USART_RQR_SBKRQ      (1u<< 1)
#define USART_RQR_ABRRQ      (1u<< 0)

#define USART_ISR_TCBGT      (1u<<25)
#define USART_ISR_TEACK      (1u<<21)
#define USART_ISR_RWU        (1u<<19)
#define USART_ISR_SBKF       (1u<<18)
#define USART_ISR_CMF        (1u<<17)
#define USART_ISR_BUSY       (1u<<16)
#define USART_ISR_ABRF       (1u<<15)
#define USART_ISR_ABRE       (1u<<14)
#define USART_ISR_EOBF       (1u<<12)
#define USART_ISR_RTOF       (1u<<11)
#define USART_ISR_CTS        (1u<<10)
#define USART_ISR_CTSIF      (1u<< 9)
#define USART_ISR_LBDF       (1u<< 8)
#define USART_ISR_TXE        (1u<< 7)
#define USART_ISR_TC         (1u<< 6)
#define USART_ISR_RXNE       (1u<< 5)
#define USART_ISR_IDLE       (1u<< 4)
#define USART_ISR_ORE        (1u<< 3)
#define USART_ISR_NF         (1u<< 2)
#define USART_ISR_FE         (1u<< 1)
#define USART_ISR_PE         (1u<< 0)

#define USART_ICR_CMCF       (1u<<17)
#define USART_ICR_EOBCF      (1u<<12)
#define USART_ICR_RTOCF      (1u<<11)
#define USART_ICR_CTSCF      (1u<< 9)
#define USART_ICR_LBDCF      (1u<< 8)
#define USART_ICR_TCBGTCF    (1u<< 7)
#define USART_ICR_TCCF       (1u<< 6)
#define USART_ICR_IDLECF     (1u<< 4)
#define USART_ICR_ORECF      (1u<< 3)
#define USART_ICR_NCF        (1u<< 2)
#define USART_ICR_FECF       (1u<< 1)
#define USART_ICR_PECF       (1u<< 0)

#define USART1_BASE 0x40011000
#define USART2_BASE 0x40004400
#define USART3_BASE 0x40004800
#define USART4_BASE 0x40004C00
#define USART5_BASE 0x40005000
#define USART6_BASE 0x40011400

#define USB_OTG_FS_BASE 0x50000000
#define USB_OTG_HS_BASE 0x40040000

/* USB High-Speed PHY Controller */
struct hsphyc {
    uint32_t pll1;     /* +00: PLL1 control */
    uint32_t _0[2];
    uint32_t tune;     /* +0C: Tuning control */
    uint32_t _1[2];
    uint32_t ldo;      /* +18: LDO control and status */
};

#define HSPHYC_PLL1_SEL(x)   ((x)<<1)
#define HSPHYC_PLL1_EN       (1u<< 0)

#define HSPHYC_TUNE_SQLBYP            (1u<<23)
#define HSPHYC_TUNE_SHTCCTCTLPROT     (1u<<22)
#define HSPHYC_TUNE_HSRXOFF(x)        ((x)<<20)
#define HSPHYC_TUNE_HSFALLPREEM       (1u<<19)
#define HSPHYC_TUNE_STAGSEL           (1u<<18)
#define HSPHYC_TUNE_HFRXGNEQEN        (1u<<17)
#define HSPHYC_TUNE_SQLCHCTL(x)       ((x)<<15)
#define HSPHYC_TUNE_HSDRVCHKZTRM(x)   ((x)<<13)
#define HSPHYC_TUNE_HSDRVCHKITRIM(x)  ((x)<< 9)
#define HSPHYC_TUNE_HSDRVRFRED        (1u<< 8)
#define HSPHYC_TUNE_FSDRVRFADJ        (1u<< 7)
#define HSPHYC_TUNE_HSDRVCURINGR      (1u<< 6)
#define HSPHYC_TUNE_HSDRVDCLEV        (1u<< 5)
#define HSPHYC_TUNE_HSDRVDCCUR        (1u<< 4)
#define HSPHYC_TUNE_HSDRVSLEW         (1u<< 3)
#define HSPHYC_TUNE_LFSCAPEN          (1u<< 2)
#define HSPHYC_TUNE_INCURRINT         (1u<< 1)
#define HSPHYC_TUNE_INCURREN          (1u<< 0)

#define HSPHYC_LDO_ENABLE    (1u<< 2)
#define HSPHYC_LDO_STATUS    (1u<< 1)
#define HSPHYC_LDO_USED      (1u<< 0)

#define HSPHYC_BASE 0x40017C00

/*
 * Local variables:
 * mode: C
 * c-file-style: "Linux"
 * c-basic-offset: 4
 * tab-width: 4
 * indent-tabs-mode: nil
 * End:
 */
