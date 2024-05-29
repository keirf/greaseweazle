
#include "c64.h"

static int decode_data_gcr(uint8_t x)
{
    switch (x)
    {
#define GCR_ENTRY(gcr, data) case gcr: return data;
#include "c64_gcr_code.h"
#undef GCR_ENTRY
    }
    return -1;
}

static int encode_data_gcr(uint8_t x)
{
    switch (x) {
#define GCR_ENTRY(gcr, data) case data: return gcr;
#include "c64_gcr_code.h"
#undef GCR_ENTRY
    }
    return -1;
}

void decode_c64_gcr(const uint8_t *input, uint8_t *output, int len)
{
    uint32_t acc = 0x10000;
    unsigned int i;

    while (--len >= 0) {
        uint16_t enc = 0;
        for (i = 0; i < 10; i++) {
            if (acc & 0x10000)
                acc = *input++ | 0x100;
            acc <<= 1;
            enc <<= 1;
            enc |= (acc >> 8) & 1;
        }
        *output++ = ((decode_data_gcr(enc >> 5) << 4)
                     | decode_data_gcr(enc & 0x1f));
    }
}

void encode_c64_gcr(const uint8_t *input, uint8_t *output, int len)
{
    uint16_t acc = 1;
    unsigned int i;

    while (--len >= 0) {
        uint8_t in = *input++;
        uint16_t enc = ((encode_data_gcr(in >> 4) << 5)
                        | encode_data_gcr(in & 15));
        for (i = 0; i < 10; i++) {
            acc <<= 1;
            acc |= (enc >> (9-i)) & 1;
            if (acc & 0x100) {
                *output++ = (uint8_t)acc;
                acc = 1;
            }
        }
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
