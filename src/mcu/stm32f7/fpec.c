/*
 * f7/fpec.c
 * 
 * STM32F73x Flash Memory Program/Erase Controller (FPEC).
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

static void fpec_wait_and_clear(void)
{
    cpu_sync();
    while (flash->sr & FLASH_SR_BSY)
        continue;
    flash->cr = 0;
}

void fpec_init(void)
{
    /* Unlock the FPEC. */
    if (flash->cr & FLASH_CR_LOCK) {
        flash->keyr = 0x45670123;
        flash->keyr = 0xcdef89ab;
    }

    fpec_wait_and_clear();
}

void fpec_page_erase(uint32_t flash_address)
{
    int sector = (flash_address - 0x08000000) >> 14;
    fpec_wait_and_clear();
    flash->cr = FLASH_CR_PSIZE(2) | FLASH_CR_SER | FLASH_CR_SNB(sector);
    flash->cr |= FLASH_CR_STRT;
    fpec_wait_and_clear();
}

void fpec_write(const void *data, unsigned int size, uint32_t flash_address)
{
    uint16_t *_f = (uint16_t *)flash_address;
    const uint16_t *_d = data;

    fpec_wait_and_clear();
    for (; size != 0; size -= 2) {
        flash->cr = FLASH_CR_PSIZE(1) | FLASH_CR_PG;
        *_f++ = *_d++; 
        fpec_wait_and_clear();
   }
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
