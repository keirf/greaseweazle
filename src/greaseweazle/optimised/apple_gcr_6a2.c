
#include "apple_gcr_6a2.h"

#define LOOKUP_LEN (MAC_SECTOR_LENGTH / 3)

int apple_gcr_6a2_decode_byte(uint8_t gcr)
{
    switch (gcr)
    {
#define GCR_ENTRY(gcr, data) case gcr: return data;
#include "apple_gcr_6a2_code.h"
#undef GCR_ENTRY
    }
    return -1;
}

void apple_gcr_6a2_decode_bytes(const uint8_t *in, uint8_t *out, int len)
{
    while (--len >= 0)
        *out++ = (uint8_t)apple_gcr_6a2_decode_byte(*in++);
}

int apple_gcr_6a2_encode_byte(uint8_t x)
{
    switch (x) {
#define GCR_ENTRY(gcr, data) case data: return gcr;
#include "apple_gcr_6a2_code.h"
#undef GCR_ENTRY
    }
    return -1;
}

void apple_gcr_6a2_encode_bytes(const uint8_t *in, uint8_t *out, int len)
{
    while (--len >= 0)
        *out++ = (uint8_t)apple_gcr_6a2_encode_byte(*in++);
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
