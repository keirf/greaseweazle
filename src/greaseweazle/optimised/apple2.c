/* 
 * Incorporates code from FluxEngine by David Given.
 * 
 * In turn this is extremely inspired by the MESS implementation, written by
 * Nathan Woods and R. Belmont:
 * https://github.com/mamedev/mame/blob/7914a6083a3b3a8c243ae6c3b8cb50b023f21e0e/src/lib/formats/ap2_dsk.cpp
 */

#include "apple_gcr_6a2.h"
#include "apple_gcr_5a3.h"
#include "apple2.h"

int extract_encoded_sector_bytes(const uint8_t *in, int in_len,
                                 uint8_t *out, int out_len)
{
    int i, j, k;
    uint8_t result;

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
                out[j++] = result;
                if (j == out_len)
                    return 0;  /* Success; found all the bytes. */
                result = 0;
            }
        }
    }
    return 1;  /* Failure; didn't find enough bytes. */
}

int decode_apple2_6a2_sector(const uint8_t *in, int in_len, uint8_t *out)
{
    int i;
    uint8_t checksum = 0;
    uint8_t mid[APPLE2_6A2_ENCODED_SECTOR_LENGTH+1];

    if (extract_encoded_sector_bytes(
            in, in_len, mid, APPLE2_6A2_ENCODED_SECTOR_LENGTH+1))
        return 1;

    in = mid;

    for (i = 0; i < APPLE2_6A2_ENCODED_SECTOR_LENGTH; i++) {
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

int decode_apple2_5a3_sector(const uint8_t *in, int in_len, uint8_t *out)
{
#define THREEBIT_COUNT 0x9a /* 'threebit' area at the start of the GCR data */
    int i, j, batch;
    uint8_t checksum = 0, value;
    uint8_t mid[APPLE2_5A3_ENCODED_SECTOR_LENGTH+1];

    if (extract_encoded_sector_bytes(
            in, in_len, mid, APPLE2_5A3_ENCODED_SECTOR_LENGTH+1))
        return 1;

    /* First, un-GCR all of the bytes in our input buffer. */
    for (i = 0; i < APPLE2_5A3_ENCODED_SECTOR_LENGTH + 1; ++i) {
        checksum ^= apple_gcr_5a3_decode_byte(mid[i]);
        mid[i] = checksum;
    }

    /* Now to assemble and emit bytes 0-254. This arrangement seems quite
     * arbitrary but is clarified somewhat by the comments and nomenclature
     * in encode_apple2_5a3_sector below. */
    for (i = 0; i < APPLE2_SECTOR_LENGTH - 1; ++i) {
        batch = i % 5;
        j = i / 5;

        /* Upper five bits */
        value = (mid[THREEBIT_COUNT + (51*batch) + (50 - j)] & 0x1f) << 3;

        /* Lower three bits */
        if (batch < 3) {
            value |= (mid[1 + (51*(2 - batch)) + j] >> 2) & 0x7;
        } else if (batch == 3) {
            value |= 0x4 & (mid[1 + 102 + j] << 1);
            value |= 0x2 & (mid[1 + 51 + j]);
            value |= 0x1 & (mid[1 + j] >> 1);
        } else {
            value |= 0x4 & (mid[1 + 102 + j] << 2);
            value |= 0x2 & (mid[1 + 51 + j] << 1);
            value |= 0x1 & (mid[1 + j]);
        }

        *out++ = value;
    }

    /* Now commit the very final byte to the output. */
    *out++ = (mid[0] & 7)
             | (mid[APPLE2_5A3_ENCODED_SECTOR_LENGTH - 1] & 0x1f) << 3;

    return checksum != 0;
#undef THREEBIT_COUNT
}

void encode_apple2_6a2_sector(const uint8_t *in, uint8_t *out)
{
#define TWOBIT_COUNT 0x56 /* 'twobit' area at the start of the GCR data */
    uint8_t tmp, checksum = 0;
    int i, value;

    for (i = 0; i < APPLE2_6A2_ENCODED_SECTOR_LENGTH; i++) {
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

void encode_apple2_5a3_sector(const uint8_t *in, uint8_t *out)
{
    /* This approach hews VERY closely to the MAME implementation. */
    uint8_t checksum = 0;
    int j, clump, batch, value;

    /* First byte out encodes the last 3 bits of the last data word. */
    value = in[255] & 0x07;
    *out++ = apple_gcr_5a3_encode_byte(checksum ^ value);
    checksum = value;

    /* Next, bytes that encode the last three bits of every byte, in an
     * intricate arrangement. For this, it helps to consider these five batches
     * of 51 interleaved bytes:
     *     Batch A: bytes 0, 5, 10, 15, ..., 250
     *     Batch B: bytes 1, 6, 11, 20, ..., 251
     *     Batch C: bytes 2, 7, 12, 25, ..., 252
     *     Batch D: bytes 3, 8, 13, 30, ..., 253
     *     Batch E: bytes 4, 9, 14, 35, ..., 254
     * Consider the j'th column of this batch table. A_j(2) means the second
     * bit of the j'th byte in batch A. We'll arrange the bits into three
     * clumps (another word for batch) as follows:
     *     Clump 2: <C_0(2), C_0(1), C_0(0), D_0(0), E_0(0)>
     *              <C_1(2), C_1(1), C_1(0), D_1(0), E_1(0)>
     *                ...
     *              <C_51(2), C_51(1), C_51(0), D_51(0), E_51(0)>
     *     Clump 1: <B_0(2), B_0(1), B_0(0), D_0(1), E_0(1)>
     *              <B_1(2), B_1(1), B_1(0), D_1(1), E_1(1)>
     *                ...
     *              <B_51(2), B_51(1), B_51(0), D_51(1), E_51(1)>
     *     Clump 0: <A_0(2), A_0(1), A_0(0), D_0(2), E_0(2)>
     *              <A_1(2), A_1(1), A_1(0), D_1(2), E_1(2)>
     *                ...
     *              <A_51(2), A_51(1), A_51(0), D_51(2), E_51(2)> */
    for (clump = 2; clump >= 0; --clump) {
        for (j = 0; j < 51; ++j) {
            value = (in[5*j + clump] & 7) << 2
                    | ((in[5*j + 3] >> (2 - clump)) & 1) << 1
                    | ((in[5*j + 4] >> (2 - clump)) & 1);
            *out++ = apple_gcr_5a3_encode_byte(checksum ^ value);
            checksum = value;
        }
    }

    /* Now to emit bytes that encode the first five bits of most data words.
     * These come in the same five batches of 51 interleaved bytes, reversed:
     *     Batch A: bytes 250, 245, 240, 235, ..., 0
     *     Batch B: bytes 251, 246, 241, 236, ..., 1
     *     Batch C: bytes 252, 247, 242, 237, ..., 2
     *     Batch D: bytes 253, 248, 243, 238, ..., 3
     *     Batch E: bytes 254, 249, 244, 239, ..., 4 */
    for (batch = 0; batch < 5; ++batch) {
        for (j = 50; j >= 0; --j) {
            value = in[5*j + batch] >> 3;
            *out++ = apple_gcr_5a3_encode_byte(checksum ^ value);
            checksum = value;
        }
    }

    /* Penultimate byte encodes the first 5 bits of the last data word. */
    value = in[APPLE2_SECTOR_LENGTH - 1] >> 3;
    *out++ = apple_gcr_5a3_encode_byte(checksum ^ value);
    checksum = value;

    /* Lastly, the checksum, which is just the encoded final byte. */
    *out++ = apple_gcr_5a3_encode_byte(checksum);
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
