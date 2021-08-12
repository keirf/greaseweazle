/*
 * board.h
 * 
 * Board definitions
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

struct board_config {
    uint8_t hse_mhz;
    bool_t hse_byp;
    bool_t hs_usb;
    bool_t flippy;
    const struct pin_mapping *user_pins;
    const struct pin_mapping *msel_pins;
};
