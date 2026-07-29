/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file    microros_transport.h
  * @brief   Custom UART transport for micro-ROS on STM32F407
  ******************************************************************************
  * @attention
  *
  * Custom UART transport implementation for micro-ROS using USART6
  * configured for 115200 baud, 8N1
  *
  ******************************************************************************
  */
/* USER CODE END Header */

#ifndef MICROROS_TRANSPORT_H
#define MICROROS_TRANSPORT_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <stdbool.h>
#include <uxr/client/profile/transport/external/external_transport.h>
#include "cmsis_os.h"

// Buffer size for transport (adjust based on memory constraints)
#define MICROROS_TRANSPORT_BUFFER_SIZE 512

/**
 * @brief Initialize the custom UART transport
 */
void microros_transport_init(void);

/**
 * @brief Set transport timeout
 * @param timeout Timeout in milliseconds
 */
void microros_transport_set_timeout(uint32_t timeout);

/**
 * @brief Open the transport (required by micro-ROS)
 * @param transport Transport handle
 * @return 0 on success
 */
int microros_transport_open(struct uxrCustomTransport *transport);

/**
 * @brief Close the transport (required by micro-ROS)
 * @param transport Transport handle
 * @return 0 on success
 */
int microros_transport_close(struct uxrCustomTransport *transport);

/**
 * @brief Write data to the transport
 * @param transport Transport handle
 * @param buf Buffer to write
 * @param len Length of buffer
 * @param err Error code output
 * @return Number of bytes written
 */
size_t microros_transport_write(struct uxrCustomTransport *transport,
                                const uint8_t *buf,
                                size_t len,
                                uint8_t *err);

/**
 * @brief Read data from the transport
 * @param transport Transport handle
 * @param buf Buffer to read into
 * @param len Length to read
 * @param err Error code output
 * @return Number of bytes read
 */
size_t microros_transport_read(struct uxrCustomTransport *transport,
                               uint8_t *buf,
                               size_t len,
                               uint8_t *err);

/**
 * @brief Get available bytes in RX buffer
 * @return Number of available bytes
 */
size_t microros_transport_available(void);

#ifdef __cplusplus
}
#endif

#endif /* MICROROS_TRANSPORT_H */