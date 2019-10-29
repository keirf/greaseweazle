/*
 * cdc_acm_protocol.h
 * 
 * Greaseweazle protocol over CDC ACM streams.
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

/* CMD_GET_INFO, length=3, 0. Returns 32 bytes after ACK. */
#define CMD_GET_INFO        0
/* CMD_SEEK, length=3, cyl# */
#define CMD_SEEK            1
/* CMD_SIDE, length=3, side# (0=bottom) */
#define CMD_SIDE            2
/* CMD_SET_DELAYS, length=2+4*2, <delay_params> */
#define CMD_SET_DELAYS      3
/* CMD_GET_DELAYS, length=2. Returns 4*2 bytes after ACK. */
#define CMD_GET_DELAYS      4
/* CMD_MOTOR, length=3, motor_state */
#define CMD_MOTOR           5
/* CMD_READ_FLUX, length=3, #revs. Returns flux readings until EOStream. */
#define CMD_READ_FLUX       6
/* CMD_WRITE_FLUX, length=2. Host follows with flux readings until EOStream. */
#define CMD_WRITE_FLUX      7
/* CMD_GET_FLUX_STATUS, length=2. Last read/write status returned in ACK. */
#define CMD_GET_FLUX_STATUS 8
/* CMD_GET_READ_INFO, length=2. Returns 7*8 bytes after ACK. */
#define CMD_GET_READ_INFO   9

/* [BOOTLOADER] CMD_UPDATE, length=6, <update_len>. 
 * Host follows with <update_len> bytes.
 * Bootloader finally returns a status byte, 0 on success. */
#define CMD_UPDATE          1

#define ACK_OKAY            0
#define ACK_BAD_COMMAND     1
#define ACK_NO_INDEX        2
#define ACK_NO_TRK0         3
#define ACK_FLUX_OVERFLOW   4
#define ACK_FLUX_UNDERFLOW  5
#define ACK_WRPROT          6

struct __packed gw_info {
    uint8_t fw_major;
    uint8_t fw_minor;
    uint8_t max_rev;
    uint8_t max_cmd;
    uint32_t sample_freq;
};

/*
 * Local variables:
 * mode: C
 * c-file-style: "Linux"
 * c-basic-offset: 4
 * tab-width: 4
 * indent-tabs-mode: nil
 * End:
 */
