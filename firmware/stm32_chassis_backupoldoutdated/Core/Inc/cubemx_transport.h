#ifndef __CUBEMX_TRANSPORT_H
#define __CUBEMX_TRANSPORT_H

#include <stdbool.h>
#include <stdint.h>

#include "main.h"

struct uxrCustomTransport;

/* Transport status/error codes for runtime diagnostics. */
#define CUBEMX_TRANSPORT_OK                     0u
#define CUBEMX_TRANSPORT_ERR_NOT_INITIALIZED    1u
#define CUBEMX_TRANSPORT_ERR_RX_START_FAILED    2u
#define CUBEMX_TRANSPORT_ERR_UART_ERROR_REARM   3u

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

bool cubemx_transport_is_active(void);
uint8_t cubemx_transport_last_error(void);

#endif /* __CUBEMX_TRANSPORT_H */