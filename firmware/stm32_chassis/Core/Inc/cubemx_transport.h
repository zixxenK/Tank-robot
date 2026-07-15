#ifndef __CUBEMX_TRANSPORT_H
#define __CUBEMX_TRANSPORT_H

#include <stdbool.h>
#include <stdint.h>

#include "main.h"

struct uxrCustomTransport;

void cubemx_transport_init(UART_HandleTypeDef *huart);
bool cubemx_transport_open(struct uxrCustomTransport *transport);
bool cubemx_transport_close(struct uxrCustomTransport *transport);
size_t cubemx_transport_write(struct uxrCustomTransport *transport,
                              const uint8_t *buf,
                              size_t len,
                              uint8_t *err);
size_t cubemx_transport_read(struct uxrCustomTransport *transport,
                             uint8_t *buf,
                             size_t len,
                             int timeout,
                             uint8_t *err);

#endif /* __CUBEMX_TRANSPORT_H */