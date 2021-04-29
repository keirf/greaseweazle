/*
 * f7/testmode.c
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

const static struct pin_mapping in_pins[] = {
    {  8, _B,  2 },
    { 26, _A,  3 },
    { 28, _A,  1 },
    { 30, _A,  0 },
    { 34, _C,  2 },
    {  0,  0,  0 }
};

const static struct pin_mapping out_pins[] = {
    { 18, _C,  4 },
    { 20, _A,  7 },
    { 22, _A,  2 },
    { 24, _A,  6 },
    { 32, _C,  3 },
    { 33, _C,  1 },
    {  0,  0,  0 }
};

void testmode_set_pin(unsigned int pin, bool_t level)
{
    int rc;
    rc = write_mapped_pin(out_pins, pin, level);
    if (rc != ACK_OKAY)
        rc = write_mapped_pin(board_config->msel_pins, pin, level);
    if (rc != ACK_OKAY)
        rc = write_mapped_pin(board_config->user_pins, pin, level);
}

bool_t testmode_get_pin(unsigned int pin)
{
    bool_t level;
    int rc = read_mapped_pin(in_pins, pin, &level);
    if (rc != ACK_OKAY)
        level = FALSE;
    return level;
}

void testmode_get_option_bytes(void *buf)
{
    memcpy(buf, (void *)0x1fff0000, 32);
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
