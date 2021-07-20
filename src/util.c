/*
 * util.c
 * 
 * General-purpose utility functions.
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

void *memset(void *s, int c, size_t n)
{
    char *p = s;

    /* Large aligned memset? */
    size_t n32 = n & ~31;
    if (n32 && !((uint32_t)p & 3)) {
        memset_fast(p, c, n32);
        p += n32;
        n &= 31;
    }

    /* Remainder/unaligned memset. */
    while (n--)
        *p++ = c;
    return s;
}

void *memcpy(void *dest, const void *src, size_t n)
{
    char *p = dest;
    const char *q = src;

    /* Large aligned copy? */
    size_t n32 = n & ~31;
    if (n32 && !(((uint32_t)p | (uint32_t)q) & 3)) {
        memcpy_fast(p, q, n32);
        p += n32;
        q += n32;
        n &= 31;
    }

    /* Remainder/unaligned copy. */
    while (n--)
        *p++ = *q++;
    return dest;
}

asm (
".global memcpy_fast, memset_fast\n"
"memcpy_fast:\n"
"    push  {r4-r10}\n"
"1:  ldmia r1!,{r3-r10}\n"
"    stmia r0!,{r3-r10}\n"
"    subs  r2,r2,#32\n"
"    bne   1b\n"
"    pop   {r4-r10}\n"
"    bx    lr\n"
"memset_fast:\n"
"    push  {r4-r10}\n"
"    uxtb  r5, r1\n"
"    mov.w r4, #0x01010101\n"
"    muls  r4, r5\n"
"    mov   r3, r4\n"
"    mov   r5, r4\n"
"    mov   r6, r4\n"
"    mov   r7, r4\n"
"    mov   r8, r4\n"
"    mov   r9, r4\n"
"    mov   r10, r4\n"
"1:  stmia r0!,{r3-r10}\n"
"    subs  r2,r2,#32\n"
"    bne   1b\n"
"    pop   {r4-r10}\n"
"    bx    lr\n"
    );

void *memmove(void *dest, const void *src, size_t n)
{
    char *p;
    const char *q;
    if (dest < src)
        return memcpy(dest, src, n);
    p = dest; p += n;
    q = src; q += n;
    while (n--)
        *--p = *--q;
    return dest;
}

int memcmp(const void *s1, const void *s2, size_t n)
{
    const char *_s1 = s1;
    const char *_s2 = s2;
    while (n--) {
        int diff = *_s1++ - *_s2++;
        if (diff)
            return diff;
    }
    return 0;
}

size_t strlen(const char *s)
{
    size_t len = 0;
    while (*s++)
        len++;
    return len;
}

size_t strnlen(const char *s, size_t maxlen)
{
    size_t len = 0;
    while (maxlen-- && *s++)
        len++;
    return len;
}

int strcmp(const char *s1, const char *s2)
{
    return strncmp(s1, s2, INT_MAX);
}

int strncmp(const char *s1, const char *s2, size_t n)
{
    while (n--) {
        int diff = *s1 - *s2;
        if (diff || !*s1)
            return diff;
        s1++; s2++;
    }
    return 0;
}

char *strcpy(char *dest, const char *src)
{
    char *p = dest;
    const char *q = src;
    while ((*p++ = *q++) != '\0')
        continue;
    return dest;
}

/* 64:32->32q division requiring 32:32->64 multiply. Cortex M3+ */
uint32_t udiv64(uint64_t dividend, uint32_t divisor)
{
    uint32_t x, q = 0;
    for (x = 1u<<31; x != 0; x >>= 1) {
        if (((uint64_t)(q|x)*divisor) <= dividend)
            q |= x;
    }
    return q;
}

/*
 * Local variables:
 * mode: C
 * c-file-style: "Linux"
 * c-basic-offset: 4
 * tab-width: 4
 * indent-tabs-mode: nil
 * End:
 */
