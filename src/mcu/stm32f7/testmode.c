/*
 * f7/testmode.c
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

const struct pin_mapping testmode_in_pins[] = {
    {  8, _B,  2 },
    { 26, _A,  3 },
    { 28, _A,  1 },
    { 30, _A,  0 },
    { 34, _C,  2 },
    {  0,  0,  0 }
};

const struct pin_mapping testmode_out_pins[] = {
    { 18, _C,  4 },
    { 20, _A,  7 },
    { 22, _A,  2 },
    { 24, _A,  6 },
    { 32, _C,  3 },
    { 33, _C,  1 },
    {  0,  0,  0 }
};

void testmode_get_option_bytes(void *buf)
{
    memcpy(buf, (void *)0x1fff0000, 32);
}

uint8_t testmode_init(void)
{
    switch (gw_info.hw_submodel) {
    case F7SM_lightning_plus:
    case F7SM_v3:
        return ACK_OKAY;
    }
    return ACK_BAD_COMMAND;
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
