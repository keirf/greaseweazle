#include <stdint.h>

#define APPLE2_SECTOR_LENGTH 256
#define APPLE2_6A2_ENCODED_SECTOR_LENGTH 342
#define APPLE2_5A3_ENCODED_SECTOR_LENGTH 410

int decode_apple2_6a2_sector(const uint8_t *in, int in_len, uint8_t *out);
void encode_apple2_6a2_sector(const uint8_t *in, uint8_t *out);
int decode_apple2_5a3_sector(const uint8_t *in, int in_len, uint8_t *out);
void encode_apple2_5a3_sector(const uint8_t *in, uint8_t *out);

/*
 * Local variables:
 * mode: C
 * c-file-style: "Linux"
 * c-basic-offset: 4
 * tab-width: 4
 * indent-tabs-mode: nil
 * End:
 */
