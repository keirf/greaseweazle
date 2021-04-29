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
 * 
 * NOTE: Commands cannot be pipelined. Do not issue a new command until the
 * previous command is completed with all expected bytes received by the host.
 */

/* CMD_GET_INFO, length=3, idx. Returns 32 bytes after ACK. */
#define CMD_GET_INFO        0
/* [BOOTLOADER] CMD_UPDATE, length=6, <update_len>. 
 * Host follows after a successful ACK response with <update_len> bytes.
 * Bootloader finally returns a status byte, 0 on success. */
/* [MAIN FIRMWARE] CMD_UPDATE, length=10, <update_len>, 0xdeafbee3.
 * Host follows after a successful ACK response with <update_len> bytes.
 * Main firmware finally returns a status byte, 0 on success. */
#define CMD_UPDATE          1
/* CMD_SEEK, length=3, cyl#. Seek to cyl# on selected drive. */
#define CMD_SEEK            2
/* CMD_HEAD, length=3, head# (0=bottom) */
#define CMD_HEAD            3
/* CMD_SET_PARAMS, length=3+nr, idx, <nr bytes> */
#define CMD_SET_PARAMS      4
/* CMD_GET_PARAMS, length=4, idx, nr_bytes. Returns nr_bytes after ACK. */
#define CMD_GET_PARAMS      5
/* CMD_MOTOR, length=4, drive#, on/off. Turn on/off a drive motor. */
#define CMD_MOTOR           6
/* CMD_READ_FLUX, length=8-12. Argument is gw_read_flux; optional fields
 * may be omitted. Returns flux readings terminating with EOStream (NUL). */
#define CMD_READ_FLUX       7
/* CMD_WRITE_FLUX, length=4. Argument is gw_write_flux.
 * Host follows the ACK with flux values terminating with EOStream (NUL).
 * Device finally returns a status byte, 0 on success.
 * No further commands should be issued until the status byte is received. */
#define CMD_WRITE_FLUX      8
/* CMD_GET_FLUX_STATUS, length=2. Last read/write status returned in ACK. */
#define CMD_GET_FLUX_STATUS 9
/* CMD_SWITCH_FW_MODE, length=3, <mode>. No response on success: The device 
 * resets into the requested mode, and the USB connection also resets. */
#define CMD_SWITCH_FW_MODE 11
/* CMD_SELECT, length=3, drive#. Select drive# as current unit. */
#define CMD_SELECT         12
/* CMD_DESELECT, length=2. Deselect current unit (if any). */
#define CMD_DESELECT       13
/* CMD_SET_BUS_TYPE, length=3, bus_type. Set the bus type. */
#define CMD_SET_BUS_TYPE   14
/* CMD_SET_PIN, length=4, pin#, level. */
#define CMD_SET_PIN        15
/* CMD_RESET, length=2. Reset all state to initial (power on) values. */
#define CMD_RESET          16
/* CMD_ERASE_FLUX, length=6. Argument is gw_erase_flux. 
 * Device returns a status byte when erasure is completed, 0 on success. 
 * No further commands should be issued until the status byte is received. */
#define CMD_ERASE_FLUX     17
/* CMD_SOURCE_BYTES, length=6. Argument is gw_sink_source_bytes. */
#define CMD_SOURCE_BYTES   18
/* CMD_SINK_BYTES, length=6. Argument is gw_sink_source_bytes. */
#define CMD_SINK_BYTES     19
/* CMD_GET_PIN, length=3, pin#. Successful ACK is followed by pin-level byte
 * (1=High, 0=Low). Unsupported pin returns ACK_BAD_PIN and no pin level. */
#define CMD_GET_PIN        20
/* CMD_TEST_MODE, length=10, 0x6e504b4e, 0x382910d3 
 * Responds ACK_OKAY and then switches to board test mode until reset. */
#define CMD_TEST_MODE      21
#define CMD_MAX            21


/*
 * CMD_SET_BUS CODES
 */
#define BUS_NONE            0
#define BUS_IBMPC           1
#define BUS_SHUGART         2


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
#define ACK_NO_UNIT         7
#define ACK_NO_BUS          8
#define ACK_BAD_UNIT        9
#define ACK_BAD_PIN        10
#define ACK_BAD_CYLINDER   11


/*
 * CONTROL-CHANNEL COMMAND SET:
 * We abuse SET_LINE_CODING requests over endpoint 0, stashing a command
 * in the baud-rate field.
 */
#define BAUD_NORMAL        9600
#define BAUD_CLEAR_COMMS  10000


/*
 * Flux stream opcodes. Preceded by 0xFF byte.
 * 
 * Argument types:
 *  N28: 28-bit non-negative integer N, encoded as 4 bytes b0,b1,b2,b3:
 *   b0 = (uint8_t)(1 | (N <<  1))
 *   b1 = (uint8_t)(1 | (N >>  6))
 *   b2 = (uint8_t)(1 | (N >> 13))
 *   b3 = (uint8_t)(1 | (N >> 20))
 */
/* FLUXOP_INDEX [CMD_READ_FLUX]
 *  Args:
 *   +4 [N28]: ticks to index, relative to sample cursor.
 *  Signals an index pulse in the read stream. Sample cursor is unaffected. */
#define FLUXOP_INDEX      1
/* FLUXOP_SPACE [CMD_READ_FLUX, CMD_WRITE_FLUX]
 *  Args:
 *   +4 [N28]: ticks to increment the sample cursor.
 *  Increments the sample cursor with no intervening flux transitions. */
#define FLUXOP_SPACE      2
/* FLUXOP_ASTABLE [CMD_WRITE_FLUX]
 *  Args:
 *   +4 [N28]: astable period.
 *  Generate regular flux transitions at specified astable period. 
 *  Duration is specified by immediately preceding FLUXOP_SPACE opcode(s). */
#define FLUXOP_ASTABLE    3


/*
 * COMMAND PACKETS
 */

/* CMD_GET_INFO, index 0 */
#define GETINFO_FIRMWARE 0
struct packed gw_info {
    uint8_t fw_major;
    uint8_t fw_minor;
    uint8_t is_main_firmware; /* == 0 -> update bootloader */
    uint8_t max_cmd;
    uint32_t sample_freq;
    uint8_t hw_model, hw_submodel;
    uint8_t usb_speed;
};
extern struct gw_info gw_info;

/* CMD_GET_INFO, index 1 */
#define GETINFO_BW_STATS 1
struct packed gw_bw_stats {
    struct packed {
        uint32_t bytes;
        uint32_t usecs;
    } min_bw, max_bw;
};

/* CMD_READ_FLUX */
struct packed gw_read_flux {
    /** MANDATORY FIELDS: **/
    /* Maximum ticks to read for (or 0, for no limit). */
    uint32_t ticks;
    /* Maximum index pulses to read (or 0, for no limit). */
    uint16_t max_index;
    /** OPTIONAL FIELDS: **/
    /* Linger time, in ticks, to continue reading after @max_index pulses. */
    uint32_t max_index_linger; /* default: 500 microseconds */
};

/* CMD_WRITE_FLUX */
struct packed gw_write_flux {
    /* If non-zero, start the write at the index pulse. */
    uint8_t cue_at_index;
    /* If non-zero, terminate the write at the next index pulse. */
    uint8_t terminate_at_index;
};

/* CMD_ERASE_FLUX */
struct packed gw_erase_flux {
    uint32_t ticks;
};

/* CMD_SINK_SOURCE_BYTES */
struct packed gw_sink_source_bytes {
    uint32_t nr_bytes;
};

/* CMD_{GET,SET}_PARAMS, index 0 */
#define PARAMS_DELAYS 0
struct packed gw_delay {
    uint16_t select_delay; /* usec */
    uint16_t step_delay;   /* usec */
    uint16_t seek_settle;  /* msec */
    uint16_t motor_delay;  /* msec */
    uint16_t watchdog;     /* msec */
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
