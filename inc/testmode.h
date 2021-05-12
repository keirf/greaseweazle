/*
 * testmode.h
 * 
 * Greaseweazle test-mode command protocol. Subject to change!
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

#define CMD_option_bytes 0
#define CMD_pins         1
#define CMD_led          2
#define CMD_test_headers 3
#define CMD_wdat_osc_on  4
#define CMD_wdat_osc_off 5

/* CMD_test_headers return code in rsp.u.x[0] */
#define TESTHEADER_success 100

struct cmd {
    uint32_t cmd;
    union {
        uint8_t pins[64/8];
        uint32_t x[28/4];
    } u;
};

struct rsp {
    union {
        uint8_t opt[32];
        uint8_t pins[64/8];
        uint32_t x[32/4];
    } u;
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
