/*
 * config.c
 * 
 * USB device and configuration descriptors.
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

const uint8_t device_descriptor[] aligned(2) = {
    18,        /* Length */
    DESC_DEVICE, /* Descriptor Type */
    0x00,0x02, /* USB 2.0 */
    2, 0, 0,   /* Class, Subclass, Protocol: CDC */
    64,        /* Max Packet Size */
    0x09,0x12, /* VID = pid.codes Open Source projects */
    0x01,0x00, /* PID = Test PID #1 */
    0,1,       /* Device Release 1.0 */
    1,2,3,     /* Manufacturer, Product, Serial */
    1          /* Number of configurations */
};

const uint8_t config_descriptor[] aligned(2) = {
    0x09, /* 0 bLength */
    DESC_CONFIGURATION, /* 1 bDescriptortype - Configuration*/
    0x43, 0x00, /* 2 wTotalLength */
    0x02, /* 4 bNumInterfaces */
    0x01, /* 5 bConfigurationValue */
    0x00, /* 6 iConfiguration - index of string */
    0x80, /* 7 bmAttributes - Bus powered */
    0xC8, /* 8 bMaxPower - 400mA */
/* CDC Communication interface */
    0x09, /* 0 bLength */
    DESC_INTERFACE, /* 1 bDescriptorType - Interface */
    0x00, /* 2 bInterfaceNumber - Interface 0 */
    0x00, /* 3 bAlternateSetting */
    0x01, /* 4 bNumEndpoints */
    2, 2, 1, /* CDC ACM, AT Command Protocol */
    0x00, /* 8 iInterface - No string descriptor */
/* Header Functional descriptor */
    0x05, /* 0 bLength */
    DESC_CS_INTERFACE, /* 1 bDescriptortype, CS_INTERFACE */
    0x00, /* 2 bDescriptorsubtype, HEADER */
    0x10, 0x01, /* 3 bcdCDC */
/* ACM Functional descriptor */
    0x04, /* 0 bLength */
    DESC_CS_INTERFACE, /* 1 bDescriptortype, CS_INTERFACE */
    0x02, /* 2 bDescriptorsubtype, ABSTRACT CONTROL MANAGEMENT */
    0x02, /* 3 bmCapabilities: Supports subset of ACM commands */
/* Union Functional descriptor */
    0x05, /* 0 bLength */
    DESC_CS_INTERFACE,/* 1 bDescriptortype, CS_INTERFACE */
    0x06, /* 2 bDescriptorsubtype, UNION */
    0x00, /* 3 bControlInterface - Interface 0 */
    0x01, /* 4 bSubordinateInterface0 - Interface 1 */
/* Call Management Functional descriptor */
    0x05, /* 0 bLength */
    DESC_CS_INTERFACE,/* 1 bDescriptortype, CS_INTERFACE */
    0x01, /* 2 bDescriptorsubtype, CALL MANAGEMENT */
    0x03, /* 3 bmCapabilities, DIY */
    0x01, /* 4 bDataInterface */
/* Notification Endpoint descriptor */
    0x07, /* 0 bLength */
    DESC_ENDPOINT, /* 1 bDescriptorType */
    0x81, /* 2 bEndpointAddress */
    0x03, /* 3 bmAttributes */
    0x40, /* 4 wMaxPacketSize - Low */
    0x00, /* 5 wMaxPacketSize - High */
    0xFF, /* 6 bInterval */
/* CDC Data interface */
    0x09, /* 0 bLength */
    DESC_INTERFACE, /* 1 bDescriptorType */
    0x01, /* 2 bInterfaceNumber */
    0x00, /* 3 bAlternateSetting */
    0x02, /* 4 bNumEndpoints */
    USB_CLASS_CDC_DATA, /* 5 bInterfaceClass */
    0x00, /* 6 bInterfaceSubClass */
    0x00, /* 7 bInterfaceProtocol*/
    0x00, /* 8 iInterface - No string descriptor*/
/* Data OUT Endpoint descriptor */
    0x07, /* 0 bLength */
    DESC_ENDPOINT, /* 1 bDescriptorType */
    0x02, /* 2 bEndpointAddress */
    0x02, /* 3 bmAttributes */
    0x40, /* 4 wMaxPacketSize - Low */
    0x00, /* 5 wMaxPacketSize - High */
    0x00, /* 6 bInterval */
/* Data IN Endpoint descriptor */
    0x07, /* 0 bLength */
    DESC_ENDPOINT, /* 1 bDescriptorType */
    0x83, /* 2 bEndpointAddress */
    0x02, /* 3 bmAttributes */
    0x40, /* 4 wMaxPacketSize - Low byte */
    0x00, /* 5 wMaxPacketSize - High byte */
    0x00 /* 6 bInterval */
};

static char serial_string[32];
char * const string_descriptors[] = {
    "\x09\x04", /* LANGID: US English */
    "Keir Fraser",
    "Greaseweazle",
    serial_string,
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
