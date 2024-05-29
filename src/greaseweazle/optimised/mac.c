/* 
 * Incorporates code from FluxEngine by David Given.
 * 
 * In turn this is extremely inspired by the MESS implementation, written by
 * Nathan Woods and R. Belmont:
 * https://github.com/mamedev/mame/blob/master/src/lib/formats/ap_dsk35.cpp
 * 
 * The MAME source file includes a nice description of the Mac track format:
 * Check it out!
 */

#include "mac.h"

#define LOOKUP_LEN (MAC_SECTOR_LENGTH / 3)

int decode_mac_sector(const uint8_t *input, uint8_t *output)
{
    const uint8_t *in = input;
    uint8_t *out = output;
    int status = 1;

    uint8_t b1[LOOKUP_LEN + 1];
    uint8_t b2[LOOKUP_LEN + 1];
    uint8_t b3[LOOKUP_LEN + 1];

    for (int i = 0; i <= LOOKUP_LEN; i++) {
        uint8_t w4 = *in++;
        uint8_t w1 = *in++;
        uint8_t w2 = *in++;
        uint8_t w3 = (i != LOOKUP_LEN) ? *in++ : 0;

        b1[i] = (w1 & 0x3F) | ((w4 << 2) & 0xC0);
        b2[i] = (w2 & 0x3F) | ((w4 << 4) & 0xC0);
        b3[i] = (w3 & 0x3F) | ((w4 << 6) & 0xC0);
    }

    /* Copy from the user's buffer to our buffer, while computing
     * the three-byte data checksum. */

    uint32_t c1 = 0;
    uint32_t c2 = 0;
    uint32_t c3 = 0;
    unsigned count = 0;
    for (;;) {

        c1 = (c1 & 0xFF) << 1;
        if (c1 & 0x0100)
            c1++;

        uint8_t val = b1[count] ^ c1;
        c3 += val;
        if (c1 & 0x0100) {
            c3++;
            c1 &= 0xFF;
        }
        *out++ = val;

        val = b2[count] ^ c3;
        c2 += val;
        if (c3 > 0xFF) {
            c2++;
            c3 &= 0xFF;
        }
        *out++ = val;

        if ((out - output) == MAC_SECTOR_LENGTH)
            break;

        val = b3[count] ^ c2;
        c1 += val;
        if (c2 > 0xFF) {
            c1++;
            c2 &= 0xFF;
        }
        *out++ = val;
        count++;
    }

    uint8_t c4 = ((c1 & 0xC0) >> 6) | ((c2 & 0xC0) >> 4) | ((c3 & 0xC0) >> 2);
    c1 &= 0x3f;
    c2 &= 0x3f;
    c3 &= 0x3f;
    c4 &= 0x3f;
    uint8_t g4 = *in++;
    uint8_t g3 = *in++;
    uint8_t g2 = *in++;
    uint8_t g1 = *in++;
    if ((g4 == c4) && (g3 == c3) && (g2 == c2) && (g1 == c1))
        status = 0;

    return status;
}

void encode_mac_sector(const uint8_t *input, uint8_t *output)
{
    const uint8_t *in = input;
    uint8_t *out = output;
    uint8_t w1, w2, w3, w4;

    uint8_t b1[LOOKUP_LEN + 1];
    uint8_t b2[LOOKUP_LEN + 1];
    uint8_t b3[LOOKUP_LEN + 1];

    uint32_t c1 = 0;
    uint32_t c2 = 0;
    uint32_t c3 = 0;
    for (int j = 0;; j++) {

        c1 = (c1 & 0xff) << 1;
        if (c1 & 0x0100)
            c1++;

        uint8_t val = *in++;
        c3 += val;
        if (c1 & 0x0100) {
            c3++;
            c1 &= 0xff;
        }
        b1[j] = (val ^ c1) & 0xff;

        val = *in++;
        c2 += val;
        if (c3 > 0xff) {
            c2++;
            c3 &= 0xff;
        }
        b2[j] = (val ^ c3) & 0xff;

        if ((in - input) == MAC_SECTOR_LENGTH)
            break;

        val = *in++;
        c1 += val;
        if (c2 > 0xff) {
            c1++;
            c2 &= 0xff;
        }
        b3[j] = (val ^ c2) & 0xff;
    }
    uint32_t c4 = ((c1 & 0xc0) >> 6) | ((c2 & 0xc0) >> 4) | ((c3 & 0xc0) >> 2);
    b3[LOOKUP_LEN] = 0;

    for (int i = 0; i <= LOOKUP_LEN; i++) {
        w1 = b1[i] & 0x3f;
        w2 = b2[i] & 0x3f;
        w3 = b3[i] & 0x3f;
        w4 = ((b1[i] & 0xc0) >> 2);
        w4 |= ((b2[i] & 0xc0) >> 4);
        w4 |= ((b3[i] & 0xc0) >> 6);

        *out++ = w4;
        *out++ = w1;
        *out++ = w2;

        if (i != LOOKUP_LEN)
            *out++ = w3;
    }

    *out++ = c4 & 0x3f;
    *out++ = c3 & 0x3f;
    *out++ = c2 & 0x3f;
    *out++ = c1 & 0x3f;
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
