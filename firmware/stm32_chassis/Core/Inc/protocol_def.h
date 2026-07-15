#ifndef PROTOCOL_DEF_H
#define PROTOCOL_DEF_H

#include <stddef.h>
#include <stdint.h>

#define PROTO_SYNC_1 0xAAu
#define PROTO_SYNC_2 0x55u

#define PROTO_FUNC_SYS 0x00u
#define PROTO_FUNC_LED 0x01u
#define PROTO_FUNC_BUZZER 0x02u
#define PROTO_FUNC_MOTOR 0x03u
#define PROTO_FUNC_PWM_SERVO 0x04u
#define PROTO_FUNC_BUS_SERVO 0x05u

#define PROTO_FUNC_HEARTBEAT 0xF0u
#define PROTO_FUNC_SELF_TEST 0xF1u
#define PROTO_FUNC_MOTOR_SET_BOTH 0x10u
#define PROTO_FUNC_EMERGENCY_STOP 0x11u
#define PROTO_FUNC_MOTOR_SET_SINGLE 0x12u

#define PROTO_MOTOR_SUBCMD_SET_SPEED 0x01u

#define PROTO_MAX_PAYLOAD_LEN 32u
#define PROTO_PARSER_TIMEOUT_MS 20u

uint8_t protocol_crc8_ccitt(const uint8_t *data, size_t len);
size_t protocol_build_frame(uint8_t function_code,
							const uint8_t *payload,
							uint8_t payload_len,
							uint8_t *out,
							size_t out_cap);

#endif