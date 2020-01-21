/*
 * defs.h
 * 
 * USB standard definitions and private interfaces.
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

/* bRequest: Standard Request Codes */
#define GET_STATUS          0
#define CLEAR_FEATURE       1
#define SET_FEATURE         3
#define SET_ADDRESS         5
#define GET_DESCRIPTOR      6
#define SET_DESCRIPTOR      7
#define GET_CONFIGURATION   8
#define SET_CONFIGURATION   9
#define GET_INTERFACE      10
#define SET_INTERFACE      11
#define SYNCH_FRAME        12

/* Descriptor Types */
#define DESC_DEVICE         1
#define DESC_CONFIGURATION  2
#define DESC_STRING         3
#define DESC_INTERFACE      4
#define DESC_ENDPOINT       5
#define DESC_DEVICE_QUALIFIER 6
#define DESC_OTHER_SPEED_CONFIGURATION 7
#define DESC_INTERFACE_POWER 8
#define DESC_CS_INTERFACE   0x24

#define USB_CLASS_CDC_DATA 0x0a

struct packed usb_device_request {
    uint8_t bmRequestType;
    uint8_t bRequest;
    uint16_t wValue;
    uint16_t wIndex;
    uint16_t wLength;
};

extern const uint8_t device_descriptor[];
extern const uint8_t config_descriptor[];

#define NR_STRING_DESC 4
extern char * const string_descriptors[];
extern char serial_string[32];

extern struct ep0 {
    struct usb_device_request req;
    uint8_t data[128];
    int data_len;
    struct {
        const uint8_t *p;
        int todo;
        bool_t trunc;
    } tx;
} ep0;
#define ep0_data_out() (!(ep0.req.bmRequestType & 0x80))
#define ep0_data_in()  (!ep0_data_out())

/* USB CDC ACM */
bool_t cdc_acm_handle_class_request(void);
bool_t cdc_acm_set_configuration(void);

/* USB Core */
void handle_rx_ep0(bool_t is_setup);
void handle_tx_ep0(void);

/* USB Hardware */
enum { EPT_CONTROL=0, EPT_ISO, EPT_BULK, EPT_INTERRUPT, EPT_DBLBUF };
void usb_configure_ep(uint8_t ep, uint8_t type, uint32_t size);
void usb_stall(uint8_t ep);
void usb_setaddr(uint8_t addr);
void hw_usb_init(void);
void hw_usb_deinit(void);

#define WARN printk

/*
 * Local variables:
 * mode: C
 * c-file-style: "Linux"
 * c-basic-offset: 4
 * tab-width: 4
 * indent-tabs-mode: nil
 * End:
 */
