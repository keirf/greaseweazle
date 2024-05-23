/* 
 * Incorporates code from FluxEngine by David Given.
 * 
 * In turn this is extremely inspired by the MESS implementation, written by
 * Nathan Woods and R. Belmont:
 * https://github.com/mamedev/mame/blob/7914a6083a3b3a8c243ae6c3b8cb50b023f21e0e/src/lib/formats/ap2_dsk.cpp
 */

#include "apple2.h"

static int decode_data_gcr(uint8_t x)
{
    switch (x)
    {
#define GCR_ENTRY(gcr, data) case gcr: return data;
#include "apple2_gcr.h"
#undef GCR_ENTRY
    }
    return -1;
}

static int encode_data_gcr(uint8_t x)
{
    switch (x) {
#define GCR_ENTRY(gcr, data) case data: return gcr;
#include "apple2_gcr.h"
#undef GCR_ENTRY
    }
    return -1;
}

int decode_apple2_sector(const uint8_t *input, uint8_t *output)
{
    unsigned int i;
    uint8_t checksum = 0;

    for (i = 0; i < APPLE2_ENCODED_SECTOR_LENGTH; i++) {
        checksum ^= decode_data_gcr(*input++);

        if (i >= 86) {
            /* 6 bit */
            output[i - 86] |= (checksum << 2);
        } else {
            /* 3 * 2 bit */
            output[i + 0] = ((checksum >> 1) & 0x01) | ((checksum << 1) & 0x02);
            output[i + 86] =
                ((checksum >> 3) & 0x01) | ((checksum >> 1) & 0x02);
            if ((i + 172) < APPLE2_SECTOR_LENGTH)
                output[i + 172] =
                    ((checksum >> 5) & 0x01) | ((checksum >> 3) & 0x02);
        }
    }

    checksum &= 0x3f;
    return (checksum != decode_data_gcr(*input));
}

void encode_apple2_sector(const uint8_t *input, uint8_t *output)
{
#define TWOBIT_COUNT 0x56 /* 'twobit' area at the start of the GCR data */
    uint8_t tmp, checksum = 0;
    int i, value;

    for (i = 0; i < APPLE2_ENCODED_SECTOR_LENGTH; i++) {
        if (i >= TWOBIT_COUNT) {
            value = input[i - TWOBIT_COUNT] >> 2;
        } else {
            tmp = input[i];
            value = ((tmp & 1) << 1) | ((tmp & 2) >> 1);

            tmp = input[i + TWOBIT_COUNT];
            value |= ((tmp & 1) << 3) | ((tmp & 2) << 1);

            if (i + 2 * TWOBIT_COUNT < APPLE2_SECTOR_LENGTH) {
                tmp = input[i + 2 * TWOBIT_COUNT];
                value |= ((tmp & 1) << 5) | ((tmp & 2) << 3);
            }
        }
        checksum ^= value;
        *output++ = encode_data_gcr(checksum);
        checksum = value;
    }
    *output++ = encode_data_gcr(checksum);
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
