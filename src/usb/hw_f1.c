/*
 * hw_f1.c
 * 
 * STM32F103 USBD.
 * 
 * Written & released by Keir Fraser <keir.xen@gmail.com>
 * 
 * This is free and unencumbered software released into the public domain.
 * See the file COPYING for more details, or visit <http://unlicense.org>.
 */

void hw_usb_init(void)
{
    usbd.init();
}

void hw_usb_deinit(void)
{
    usbd.deinit();
}

bool_t hw_has_highspeed(void)
{
    return usbd.has_highspeed();
}

bool_t usb_is_highspeed(void)
{
    return usbd.is_highspeed();
}

int ep_rx_ready(uint8_t epnr)
{
    return usbd.ep_rx_ready(epnr);
}

bool_t ep_tx_ready(uint8_t epnr)
{
    return usbd.ep_tx_ready(epnr);
}
 
void usb_read(uint8_t epnr, void *buf, uint32_t len)
{
    usbd.read(epnr, buf, len);
}

void usb_write(uint8_t epnr, const void *buf, uint32_t len)
{
    usbd.write(epnr, buf, len);
}
 
void usb_stall(uint8_t epnr)
{
    usbd.stall(epnr);
}

void usb_configure_ep(uint8_t epnr, uint8_t type, uint32_t size)
{
    usbd.configure_ep(epnr, type, size);
}

void usb_setaddr(uint8_t addr)
{
    usbd.setaddr(addr);
}

void usb_process(void)
{
    usbd.process();
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
