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


/*
 * GREASEWEAZLE COMMAND SET
 */

/* CMD_GET_INFO, length=3, 0. Returns 32 bytes after ACK. */
#define CMD_GET_INFO        0
/* CMD_SEEK, length=3, cyl# */
#define CMD_SEEK            1
/* CMD_SIDE, length=3, side# (0=bottom) */
#define CMD_SIDE            2
/* CMD_SET_PARAMS, length=3+nr, idx, <nr bytes> */
#define CMD_SET_PARAMS      3
/* CMD_GET_PARAMS, length=4, idx, nr_bytes. Returns nr_bytes after ACK. */
#define CMD_GET_PARAMS      4
/* CMD_MOTOR, length=3, motor_mask */
#define CMD_MOTOR           5
/* CMD_READ_FLUX, length=2-3. Optionally include all or part of gw_read_flux.
 * Returns flux readings until EOStream. */
#define CMD_READ_FLUX       6
/* CMD_WRITE_FLUX, length=2-7. Optionally include all or part of gw_write_flux.
 * Host follows with flux readings until EOStream. */
#define CMD_WRITE_FLUX      7
/* CMD_GET_FLUX_STATUS, length=2. Last read/write status returned in ACK. */
#define CMD_GET_FLUX_STATUS 8
/* CMD_GET_INDEX_TIMES, length=4, first, nr.
 * Returns nr*4 bytes after ACK. */
#define CMD_GET_INDEX_TIMES 9
/* CMD_SELECT, length=3, select_mask */
#define CMD_SELECT         10
/* CMD_SWITCH_FW_MODE, length=3, <mode> */
#define CMD_SWITCH_FW_MODE 11
#define CMD_MAX            11

/* [BOOTLOADER] CMD_UPDATE, length=6, <update_len>. 
 * Host follows with <update_len> bytes.
 * Bootloader finally returns a status byte, 0 on success. */
#define CMD_UPDATE          1


/*
 * ACK RETURN CODES
 */
#define ACK_OKAY            0
#define ACK_BAD_COMMAND     1
#define ACK_NO_INDEX        2
#define ACK_NO_TRK0         3
#define ACK_FLUX_OVERFLOW   4
#define ACK_FLUX_UNDERFLOW  5
#define ACK_WRPROT          6


/*
 * CONTROL-CHANNEL COMMAND SET:
 * We abuse SET_LINE_CODING requests over endpoint 0, stashing a command
 * in the baud-rate field.
 */
#define BAUD_NORMAL        9600
#define BAUD_CLEAR_COMMS  10000


/*
 * COMMAND PACKETS
 */

/* CMD_GET_INFO, index 0 */
struct packed gw_info {
    uint8_t fw_major;
    uint8_t fw_minor;
    uint8_t max_index;
    uint8_t max_cmd;
    uint32_t sample_freq;
    uint16_t hw_type;
};

/* CMD_READ_FLUX */
struct packed gw_read_flux {
    uint8_t nr_idx; /* default: 2 */
};

/* CMD_WRITE_FLUX */
struct packed gw_write_flux {
    uint32_t index_delay_ticks; /* default: 0 */
    uint8_t terminate_at_index; /* default: 0 */
};

/* CMD_{GET,SET}_PARAMS, index 0 */
#define PARAMS_DELAYS 0
struct packed gw_delay {
    uint16_t select_delay; /* usec */
    uint16_t step_delay;   /* usec */
    uint16_t seek_settle;  /* msec */
    uint16_t motor_delay;  /* msec */
    uint16_t auto_off;     /* msec */
};

/* CMD_SWITCH_FW_MODE */
#define FW_MODE_BOOTLOADER 0
#define FW_MODE_NORMAL     1

/*
 * Local variables:
 * mode: C
 * c-file-style: "Linux"
 * c-basic-offset: 4
 * tab-width: 4
 * indent-tabs-mode: nil
 * End:
 */
