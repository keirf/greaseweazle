#include <stdint.h>

int apple_gcr_6a2_decode_byte(uint8_t gcr);
void apple_gcr_6a2_decode_bytes(const uint8_t *in, uint8_t *out, int len);
int apple_gcr_6a2_encode_byte(uint8_t x);
void apple_gcr_6a2_encode_bytes(const uint8_t *in, uint8_t *out, int len);

/*
 * Local variables:
 * mode: C
 * c-file-style: "Linux"
 * c-basic-offset: 4
 * tab-width: 4
 * indent-tabs-mode: nil
 * End:
 */
