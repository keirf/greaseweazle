#include <stdint.h>

#define MAC_SECTOR_LENGTH 524
#define MAC_ENCODED_SECTOR_LENGTH 703

void gcr_decode_bytes(const uint8_t *input, uint8_t *output, int len);
void gcr_encode_bytes(const uint8_t *input, uint8_t *output, int len);

int decode_mac_sector(const uint8_t *input, uint8_t *output);
void encode_mac_sector(const uint8_t *input, uint8_t *output);

/*
 * Local variables:
 * mode: C
 * c-file-style: "Linux"
 * c-basic-offset: 4
 * tab-width: 4
 * indent-tabs-mode: nil
 * End:
 */
