/* 
 * Incorporates code from FluxEngine by David Given.
 * 
 * In turn this is extremely inspired by the MESS implementation, written by
 * Nathan Woods and R. Belmont:
 * https://github.com/mamedev/mame/blob/7914a6083a3b3a8c243ae6c3b8cb50b023f21e0e/src/lib/formats/ap2_dsk.cpp
 */

#include "apple_gcr_6a2.h"
#include "apple2.h"

int decode_apple2_sector(const uint8_t *in, int in_len, uint8_t *out)
{
    int i, j, k;
    uint8_t result, checksum = 0;
    uint8_t mid[APPLE2_ENCODED_SECTOR_LENGTH+1];

    /* Sometimes there's a 1-bit gap between APPLE2_DATA_RECORD and the data
     * itself.  This has been seen on real world disks such as the Apple II
     * Operating System Kit from Apple2Online. However, I haven't seen it
     * described in any of the various references.
     *
     * This extra '0' bit would not affect the real disk interface, as it was
     * a '1' reaching the top bit of a shift register that triggered a byte to
     * be available, but it affects the way the data is read here.
     *
     * While the floppies tested only seemed to need this applied to the first
     * byte of the data record, applying it consistently to all of them
     * doesn't seem to hurt, and simplifies the code. */
    j = 0;
    result = 0;
    for (i = 0; i < in_len; i++) {
        uint8_t x = in[i];
        for (k = 0; k < 8; k++) {
            result = (result << 1) | (x >> 7);
            x <<= 1;
            if (result & 0x80) {
                mid[j++] = result;
                if (j == APPLE2_ENCODED_SECTOR_LENGTH+1)
                    goto found;
                result = 0;
            }
        }
    }

    return 1;

found:
    in = mid;

    for (i = 0; i < APPLE2_ENCODED_SECTOR_LENGTH; i++) {
        checksum ^= apple_gcr_6a2_decode_byte(*in++);

        if (i >= 86) {
            /* 6 bit */
            out[i - 86] |= (checksum << 2);
        } else {
            /* 3 * 2 bit */
            out[i + 0] = ((checksum >> 1) & 0x01) | ((checksum << 1) & 0x02);
            out[i + 86] =
                ((checksum >> 3) & 0x01) | ((checksum >> 1) & 0x02);
            if ((i + 172) < APPLE2_SECTOR_LENGTH)
                out[i + 172] =
                    ((checksum >> 5) & 0x01) | ((checksum >> 3) & 0x02);
        }
    }

    checksum &= 0x3f;
    return (checksum != apple_gcr_6a2_decode_byte(*in));
}

void encode_apple2_sector(const uint8_t *in, uint8_t *out)
{
#define TWOBIT_COUNT 0x56 /* 'twobit' area at the start of the GCR data */
    uint8_t tmp, checksum = 0;
    int i, value;

    for (i = 0; i < APPLE2_ENCODED_SECTOR_LENGTH; i++) {
        if (i >= TWOBIT_COUNT) {
            value = in[i - TWOBIT_COUNT] >> 2;
        } else {
            tmp = in[i];
            value = ((tmp & 1) << 1) | ((tmp & 2) >> 1);

            tmp = in[i + TWOBIT_COUNT];
            value |= ((tmp & 1) << 3) | ((tmp & 2) << 1);

            if (i + 2 * TWOBIT_COUNT < APPLE2_SECTOR_LENGTH) {
                tmp = in[i + 2 * TWOBIT_COUNT];
                value |= ((tmp & 1) << 5) | ((tmp & 2) << 3);
            }
        }
        checksum ^= value;
        *out++ = apple_gcr_6a2_encode_byte(checksum);
        checksum = value;
    }
    *out++ = apple_gcr_6a2_encode_byte(checksum);
#undef TWOBIT_COUNT
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
