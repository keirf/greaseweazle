/*
 * intrinsics.h
 * 
 * Compiler intrinsics for ARMv7-M core.
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

struct exception_frame {
    uint32_t r0, r1, r2, r3, r12, lr, pc, psr;
};

#define _STR(x) #x
#define STR(x) _STR(x)

/* Force a compilation error if condition is true */
#define BUILD_BUG_ON(cond) ({ _Static_assert(!(cond), "!(" #cond ")"); })

#define aligned(x) __attribute__((aligned(x)))
#define packed __attribute((packed))
#define always_inline __inline__ __attribute__((always_inline))
#define noinline __attribute__((noinline))

#define likely(x)     __builtin_expect(!!(x),1)
#define unlikely(x)   __builtin_expect(!!(x),0)

#define illegal() asm volatile (".short 0xde00");

#define barrier() asm volatile ("" ::: "memory")
#define cpu_sync() asm volatile("dsb; isb" ::: "memory")
#define cpu_relax() asm volatile ("nop" ::: "memory")

#define sv_call(imm) asm volatile ( "svc %0" : : "i" (imm) )

#define read_special(reg) ({                        \
    uint32_t __x;                                   \
    asm volatile ("mrs %0,"#reg : "=r" (__x) ::);   \
    __x;                                            \
})

#define write_special(reg,val) ({                   \
    uint32_t __x = (uint32_t)(val);                 \
    asm volatile ("msr "#reg",%0" :: "r" (__x) :);  \
})

/* CONTROL[1] == 0 => running on Master Stack (Exception Handler mode). */
#define CONTROL_SPSEL 2
#define in_exception() (!(read_special(control) & CONTROL_SPSEL))

#define global_disable_exceptions() \
    asm volatile ("cpsid f; cpsid i" ::: "memory")
#define global_enable_exceptions() \
    asm volatile ("cpsie f; cpsie i" ::: "memory")

/* NB. IRQ disable via CPSID/MSR is self-synchronising. No barrier needed. */
#define IRQ_global_disable() asm volatile ("cpsid i" ::: "memory")
#define IRQ_global_enable() asm volatile ("cpsie i" ::: "memory")

#define IRQ_global_save(flags) ({               \
    (flags) = read_special(primask) & 1;        \
    IRQ_global_disable(); })
#define IRQ_global_restore(flags) ({            \
    if (flags == 0) IRQ_global_enable(); })

/* Save/restore IRQ priority levels. 
 * NB. IRQ disable via MSR is self-synchronising. I have confirmed this on 
 * Cortex-M3: any pending IRQs are handled before they are disabled by 
 * a BASEPRI update. Hence no barrier is needed here. */
#define IRQ_save(newpri) ({                         \
        uint8_t __newpri = (newpri)<<4;             \
        uint8_t __oldpri = read_special(basepri);   \
        if (!__oldpri || (__oldpri > __newpri))     \
            write_special(basepri, __newpri);       \
        __oldpri; })
/* NB. Same as CPSIE, any pending IRQ enabled by this BASEPRI update may 
 * execute a couple of instructions after the MSR instruction. This has been
 * confirmed on Cortex-M3. */
#define IRQ_restore(oldpri) write_special(basepri, (oldpri))

/* Cortex initialisation */
void cortex_init(void);

#if defined(CORTEX_M7)

/* Cache operations */
void icache_invalidate_all(void);
void icache_enable(void);
void dcache_invalidate_all(void);
void dcache_clear_and_invalidate_all(void);
void dcache_enable(void);
void dcache_disable(void);

#elif defined(CORTEX_M3)

/* No caches in Cortex M3 */
#define icache_invalidate_all() ((void)0)
#define icache_enable() ((void)0)
#define dcache_invalidate_all() ((void)0)
#define dcache_clear_and_invalidate_all() ((void)0)
#define dcache_enable() ((void)0)
#define dcache_disable() ((void)0)

#endif

/*
 * Local variables:
 * mode: C
 * c-file-style: "Linux"
 * c-basic-offset: 4
 * tab-width: 4
 * indent-tabs-mode: nil
 * End:
 */
