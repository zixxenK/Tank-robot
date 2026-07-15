#ifndef PROTOCOL_GATEWAY_H
#define PROTOCOL_GATEWAY_H

#include <stddef.h>
#include <stdint.h>

typedef void (*protocol_gateway_command_handler_t)(uint8_t function_code,
                                                   const uint8_t *payload,
                                                   uint8_t payload_len);

void protocol_gateway_reset(void);
void protocol_gateway_set_handler(protocol_gateway_command_handler_t handler);

/*
 * Consumes one byte from UART stream.
 * - bytes_to_forward is filled with bytes that are not part of a valid binary frame
 *   and should continue to downstream consumers (micro-ROS transport ring).
 * - Returns number of bytes written to bytes_to_forward.
 */
size_t protocol_gateway_consume_byte(uint8_t byte,
                                     uint32_t now_ms,
                                     uint8_t *bytes_to_forward,
                                     size_t max_forward_len);

#endif