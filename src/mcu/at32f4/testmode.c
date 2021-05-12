/*
 * at32f4xx/testmode.c
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

const struct pin_mapping testmode_in_pins[] = {
    {  8, _B, 10 },
    { 26, _B,  4 },
    { 28, _B,  3 },
    { 30, _A, 15 },
    { 34, _B, 15 },
    {  0,  0,  0 }
};

const struct pin_mapping testmode_out_pins[] = {
    { 18, _B,  8 },
    { 20, _B,  6 },
    { 22, _A,  2 },
    { 24, _B,  7 },
    { 32, _B,  5 },
    { 33, _B, 14 },
    {  0,  0,  0 }
};

void testmode_get_option_bytes(void *buf)
{
    memcpy(buf, (void *)0x1ffff800, 32);
}

uint8_t testmode_init(void)
{
    return ACK_OKAY;
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
