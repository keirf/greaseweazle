/*
 * at32f4xx/testmode.c
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

const static struct pin_mapping in_pins[] = {
    {  8, _B, 10 },
    { 26, _B,  4 },
    { 28, _B,  3 },
    { 30, _A, 15 },
    { 34, _B, 15 },
    {  0,  0,  0 }
};

const static struct pin_mapping out_pins[] = {
    { 18, _B,  8 },
    { 20, _B,  6 },
    { 22, _A,  2 },
    { 24, _B,  7 },
    { 32, _B,  5 },
    { 33, _B, 14 },
    {  0,  0,  0 }
};

extern const struct pin_mapping msel_pins[];
extern const struct pin_mapping user_pins[];

void testmode_set_pin(unsigned int pin, bool_t level)
{
    int rc;
    rc = write_mapped_pin(out_pins, pin, level);
    if (rc != ACK_OKAY)
        rc = write_mapped_pin(msel_pins, pin, level);
    if (rc != ACK_OKAY)
        rc = write_mapped_pin(user_pins, pin, level);
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
    memcpy(buf, (void *)0x1ffff800, 16);
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
