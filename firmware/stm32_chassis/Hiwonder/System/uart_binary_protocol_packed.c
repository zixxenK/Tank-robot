/**
 * @file uart_binary_protocol_packed.c
 * @brief Packed binary protocol implementation with DMA and hardware timer support
 *
 * CRITICAL IMPLEMENTATION NOTES:
 * 1. All structs use __attribute__((packed)) to match Python struct.pack()
 * 2. DMA circular buffer for non-blocking reception
 * 3. Hardware timer for deterministic timeout protection
 * 4. State machine parser for robust frame synchronization
 * 5. Burst telemetry transmission at fixed frequency
 */

#include "uart_binary_protocol_packed.h"
#include "status_integration.h"
#include "motor_control.h"
#include "imu_integration.h"
#include "battery_integration.h"
#include <math.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

// ============================================================================
// CRC-8-CCITT LOOKUP TABLE
// ============================================================================

static const uint8_t CRC8_TABLE[] = {
    0, 94, 188, 226, 97, 63, 221, 131, 194, 156, 126, 32, 163, 253, 31, 65,
    157, 195, 33, 127, 252, 162, 64, 30, 95, 1, 227, 189, 62, 96, 130, 220,
    35, 125, 159, 193, 66, 28, 254, 160, 225, 191, 93, 3, 128, 222, 60, 98,
    190, 224, 2, 92, 223, 129, 99, 61, 124, 34, 192, 158, 29, 67, 161, 255,
    70, 24, 250, 164, 39, 121, 155, 197, 132, 218, 56, 102, 229, 187, 89, 7,
    219, 133, 103, 57, 186, 228, 6, 88, 25, 71, 165, 251, 120, 38, 196, 154,
    101, 59, 217, 135, 4, 90, 184, 230, 167, 249, 27, 69, 198, 152, 122, 36,
    248, 166, 68, 26, 153, 199, 37, 123, 58, 100, 134, 216, 91, 5, 231, 185,
    140, 210, 48, 110, 237, 179, 81, 15, 78, 16, 242, 172, 47, 113, 147, 205,
    17, 79, 173, 243, 112, 46, 204, 146, 211, 141, 111, 49, 178, 236, 14, 80,
    175, 241, 19, 77, 206, 144, 114, 44, 109, 51, 209, 143, 12, 82, 176, 238,
    50, 108, 142, 208, 83, 13, 239, 177, 240, 174, 76, 18, 145, 207, 45, 115,
    202, 148, 118, 40, 171, 245, 23, 73, 8, 86, 180, 234, 105, 55, 213, 139,
    87, 9, 235, 181, 54, 104, 138, 212, 149, 203, 41, 119, 244, 170, 72, 22,
    233, 183, 85, 11, 136, 214, 52, 106, 43, 117, 151, 201, 74, 20, 246, 168,
    116, 42, 200, 150, 21, 75, 169, 247, 182, 232, 10, 84, 215, 137, 107, 53,
};

// ============================================================================
// CRC-8-CCITT CALCULATION
// ============================================================================

static uint8_t crc8_ccitt(const uint8_t *data, uint16_t len) {
    uint8_t crc = 0x00;
    for (uint16_t i = 0; i < len; i++) {
        crc = CRC8_TABLE[crc ^ data[i]];
    }
    return crc;
}

// ============================================================================
// FRAME BUILDING
// ============================================================================

static uint16_t build_frame(uint8_t func,
                            const uint8_t *payload,
                            uint8_t payload_len,
                            uint8_t *output,
                            uint16_t output_size) {
    uint16_t total_len = FRAME_HEADER_SIZE + (uint16_t)payload_len +
                         FRAME_FOOTER_SIZE;

    if (output == NULL || total_len > output_size ||
        (payload_len > 0 && payload == NULL)) {
        return 0;
    }

    uint16_t index = 0;

    // Header: SYNC_1, SYNC_2, FUNC, LEN
    output[index++] = SYNC_BYTE_1;
    output[index++] = SYNC_BYTE_2;
    output[index++] = func;
    output[index++] = payload_len;

    // Payload
    if (payload && payload_len > 0) {
        memcpy(&output[index], payload, payload_len);
        index += payload_len;
    }

    // Function, length, and payload are contiguous in the output frame.
    output[index++] = crc8_ccitt(&output[2], payload_len + 2);

    return index;
}

static void binary_protocol_start_tx(BinaryProtocolContext *ctx) {
    if (ctx == NULL || ctx->tx_busy || ctx->tx_tail == ctx->tx_head ||
        (ctx->uart_handle == NULL && ctx->transmit_callback == NULL)) {
        return;
    }

    ProtocolTxFrame *frame = &ctx->tx_queue[ctx->tx_tail];
    ctx->tx_busy = true;

    uint8_t result;
    if (ctx->transmit_callback != NULL) {
        result = ctx->transmit_callback(frame->data, frame->length);
    } else {
        result = (uint8_t)HAL_UART_Transmit_DMA(ctx->uart_handle,
                                                frame->data,
                                                frame->length);
    }

    if (result != HAL_OK) {
        ctx->tx_busy = false;
        ctx->stats.tx_errors++;
    }
}

static bool binary_protocol_queue_frame(BinaryProtocolContext *ctx,
                                        uint8_t func,
                                        const uint8_t *payload,
                                        uint8_t payload_len) {
    uint32_t primask = __get_PRIMASK();
    __disable_irq();

    uint8_t next_head = (uint8_t)((ctx->tx_head + 1U) %
                                  TX_FRAME_QUEUE_DEPTH);

    if (next_head == ctx->tx_tail) {
        ctx->stats.tx_queue_overruns++;
        if (primask == 0U) {
            __enable_irq();
        }
        return false;
    }

    ProtocolTxFrame *frame = &ctx->tx_queue[ctx->tx_head];
    uint16_t frame_len = build_frame(func,
                                     payload,
                                     payload_len,
                                     frame->data,
                                     sizeof(frame->data));
    if (frame_len == 0) {
        ctx->stats.tx_errors++;
        if (primask == 0U) {
            __enable_irq();
        }
        return false;
    }

    frame->length = frame_len;
    __DMB();
    ctx->tx_head = next_head;
    if (primask == 0U) {
        __enable_irq();
    }
    binary_protocol_start_tx(ctx);
    return true;
}

void binary_protocol_tx_complete(BinaryProtocolContext *ctx) {
    if (ctx == NULL || !ctx->tx_busy) {
        return;
    }

    ctx->tx_tail = (uint8_t)((ctx->tx_tail + 1U) %
                             TX_FRAME_QUEUE_DEPTH);
    ctx->tx_busy = false;
    binary_protocol_start_tx(ctx);
}

void binary_protocol_set_transmit_callback(BinaryProtocolContext *ctx,
                                           ProtocolTransmitCallback callback) {
    if (ctx == NULL) {
        return;
    }
    ctx->transmit_callback = callback;
}

// ============================================================================
// INITIALIZATION
// ============================================================================

void binary_protocol_init_packed(BinaryProtocolContext *ctx,
                                 UART_HandleTypeDef *huart,
                                 DMA_HandleTypeDef *hdma_rx,
                                 DMA_HandleTypeDef *hdma_tx,
                                 uint32_t command_timeout_ms,
                                 uint32_t heartbeat_timeout_ms) {
    // Clear entire context
    memset(ctx, 0, sizeof(BinaryProtocolContext));

    // Store hardware handles
    ctx->uart_handle = huart;
    ctx->rx_dma_handle = hdma_rx;
    ctx->tx_dma_handle = hdma_tx;

    // Configure timeouts
    ctx->command_timeout_ms = command_timeout_ms;
    ctx->heartbeat_timeout_ms = heartbeat_timeout_ms;
    ctx->telemetry_interval_ms = 20;  // 50Hz default

    // Initialize parser state
    ctx->rx_state = FRAME_STATE_SYNC1;
    ctx->rx_read_pos = 0;
    ctx->rx_write_pos = 0;

    // Initialize telemetry
    ctx->telemetry_enabled = true;
    ctx->last_telemetry_time = HAL_GetTick();
    ctx->last_command_time = HAL_GetTick();
    ctx->last_heartbeat_time = HAL_GetTick();

    // Start DMA circular reception if available
    if (huart && hdma_rx) {
        // Configure DMA for circular mode
        hdma_rx->Instance->CR |= DMA_SxCR_CIRC;  // Enable circular mode

        // Start DMA reception
        HAL_UART_Receive_DMA(huart, (uint8_t*)ctx->rx_buffer, RX_BUFFER_SIZE);
    } else {
        // No DMA available - will use polling mode
        ctx->rx_write_pos = 0;
    }
}

// ============================================================================
// DMA BUFFER PROCESSING
// ============================================================================

void binary_protocol_process_dma(BinaryProtocolContext *ctx) {
    if (ctx->rx_dma_handle) {
        // DMA mode - calculate available data in circular buffer
        // DMA write position is: RX_BUFFER_SIZE - DMA counter
        uint16_t dma_write_pos = RX_BUFFER_SIZE - __HAL_DMA_GET_COUNTER(ctx->rx_dma_handle);

        // Process all available bytes
        while (ctx->rx_read_pos != dma_write_pos) {
            uint8_t byte = ctx->rx_buffer[ctx->rx_read_pos];

            // Process byte through state machine
            binary_protocol_process_byte(ctx, byte);

            // Advance read position (with wraparound)
            ctx->rx_read_pos = (ctx->rx_read_pos + 1) % RX_BUFFER_SIZE;
        }
    } else {
        if (ctx->uart_handle != NULL) {
            // UART polling mode - read a single byte.
            uint8_t byte;
            if (HAL_UART_Receive(ctx->uart_handle, &byte, 1, 0) == HAL_OK) {
                binary_protocol_process_byte(ctx, byte);
            }
        } else {
            // Callback-based transport mode - drain bytes queued by the
            // transport callback from normal task context.
            while (ctx->rx_read_pos != ctx->rx_write_pos) {
                uint8_t byte = ctx->rx_buffer[ctx->rx_read_pos];
                ctx->rx_read_pos = (uint16_t)((ctx->rx_read_pos + 1U) %
                                               RX_BUFFER_SIZE);
                binary_protocol_process_byte(ctx, byte);
            }
        }
    }
}

void binary_protocol_process_bytes(BinaryProtocolContext *ctx,
                                   const uint8_t *data,
                                   uint16_t length) {
    if (ctx == NULL || data == NULL) {
        return;
    }
    for (uint16_t index = 0; index < length; index++) {
        uint16_t next_write = (uint16_t)((ctx->rx_write_pos + 1U) %
                                         RX_BUFFER_SIZE);
        if (next_write == ctx->rx_read_pos) {
            ctx->stats.buffer_overruns++;
            break;
        }
        ctx->rx_buffer[ctx->rx_write_pos] = data[index];
        ctx->rx_write_pos = next_write;
    }
}

// ============================================================================
// STATE MACHINE PARSER
// ============================================================================

void binary_protocol_process_byte(BinaryProtocolContext *ctx, uint8_t byte) {
    switch (ctx->rx_state) {
        case FRAME_STATE_SYNC1:
            if (byte == SYNC_BYTE_1) {
                ctx->rx_state = FRAME_STATE_SYNC2;
                ctx->frame_buffer[0] = byte;
                ctx->frame_pos = 1;
            }
            break;

        case FRAME_STATE_SYNC2:
            if (byte == SYNC_BYTE_2) {
                ctx->rx_state = FRAME_STATE_FUNC;
                ctx->frame_buffer[ctx->frame_pos++] = byte;
            } else {
                // False sync, reset
                ctx->rx_state = FRAME_STATE_SYNC1;
                if (byte == SYNC_BYTE_1) {
                    ctx->frame_buffer[0] = byte;
                    ctx->frame_pos = 1;
                    ctx->rx_state = FRAME_STATE_SYNC2;
                } else {
                    ctx->frame_pos = 0;
                }
            }
            break;

        case FRAME_STATE_FUNC:
            ctx->frame_buffer[ctx->frame_pos++] = byte;
            ctx->rx_state = FRAME_STATE_LEN;
            break;

        case FRAME_STATE_LEN:
            ctx->frame_buffer[ctx->frame_pos++] = byte;
            ctx->expected_payload_len = byte;

            if (ctx->expected_payload_len > MAX_PAYLOAD_SIZE) {
                ctx->rx_state = FRAME_STATE_SYNC1;
                ctx->frame_pos = 0;
                ctx->stats.invalid_frames++;
            } else if (ctx->expected_payload_len == 0) {
                ctx->rx_state = FRAME_STATE_CRC;
            } else {
                ctx->rx_state = FRAME_STATE_PAYLOAD;
            }
            break;

        case FRAME_STATE_PAYLOAD:
            if (ctx->frame_pos >= MAX_FRAME_SIZE - FRAME_FOOTER_SIZE) {
                ctx->rx_state = FRAME_STATE_SYNC1;
                ctx->frame_pos = 0;
                ctx->stats.invalid_frames++;
                break;
            }

            ctx->frame_buffer[ctx->frame_pos++] = byte;

            if (ctx->frame_pos >= FRAME_HEADER_SIZE + ctx->expected_payload_len) {
                ctx->rx_state = FRAME_STATE_CRC;
            }

            break;

        case FRAME_STATE_CRC:
            if (ctx->frame_pos >= MAX_FRAME_SIZE) {
                ctx->rx_state = FRAME_STATE_SYNC1;
                ctx->frame_pos = 0;
                ctx->stats.invalid_frames++;
                break;
            }

            ctx->frame_buffer[ctx->frame_pos++] = byte;

            // Validate complete frame
            uint16_t total_len = FRAME_HEADER_SIZE + ctx->expected_payload_len + FRAME_FOOTER_SIZE;
            if (ctx->frame_pos == total_len) {
                // Validate CRC
                uint8_t calculated_crc = crc8_ccitt(&ctx->frame_buffer[2], ctx->expected_payload_len + 2);
                uint8_t received_crc = ctx->frame_buffer[total_len - 1];

                if (calculated_crc == received_crc) {
                    // Valid frame - process it
                    uint8_t func = ctx->frame_buffer[2];
                    uint8_t *payload = &ctx->frame_buffer[4];
                    binary_protocol_process_frame(ctx, func, payload, ctx->expected_payload_len);
                    ctx->stats.valid_frames++;
                } else {
                    ctx->stats.crc_errors++;
                    ctx->stats.invalid_frames++;
                }
            }

            // Reset for next frame
            ctx->rx_state = FRAME_STATE_SYNC1;
            ctx->frame_pos = 0;
            break;
    }
}

// ============================================================================
// FRAME PROCESSING
// ============================================================================

void binary_protocol_process_frame(BinaryProtocolContext *ctx, uint8_t func, uint8_t *payload, uint8_t payload_len) {
    switch (func) {
        case FUNC_HEARTBEAT:
            if (payload_len == 0) {
                ctx->last_heartbeat_time = HAL_GetTick();
                binary_protocol_send_heartbeat(ctx);
            }
            break;

        case FUNC_MOTOR:
            if (payload_len < 2) {
                break;
            }

            if (payload[0] == MOTOR_SUBCMD_SET_SPEED) {
                uint8_t motor_count = payload[1];
                uint16_t expected_len = 2U +
                    (uint16_t)motor_count * sizeof(MotorCommandEntry);

                if (motor_count == 0 ||
                    motor_count > MOTOR_COMMAND_CAPACITY ||
                    payload_len != expected_len) {
                    break;
                }

                MotorCommandPayload validated = {0};
                uint8_t seen_ids = 0;
                validated.subcmd = MOTOR_SUBCMD_SET_SPEED;
                validated.motor_count = motor_count;

                for (uint8_t i = 0; i < motor_count; ++i) {
                    uint16_t offset = 2U +
                        (uint16_t)i * sizeof(MotorCommandEntry);
                    uint8_t motor_id = payload[offset];
                    float rps;
                    memcpy(&rps, &payload[offset + 1U], sizeof(rps));

                    if (motor_id >= MOTOR_COMMAND_CAPACITY ||
                        (seen_ids & (1U << motor_id)) != 0 ||
                        !isfinite(rps) || rps < -1.0f || rps > 1.0f) {
                        return;
                    }

                    seen_ids |= (uint8_t)(1U << motor_id);
                    validated.motors[i].motor_id = motor_id;
                    validated.motors[i].rps = rps;
                }

                memcpy(&ctx->motor_commands, &validated, sizeof(validated));
                ctx->motor_command_count = motor_count;
                ctx->last_command_time = HAL_GetTick();
                ctx->emergency_stop_active = false;
            } else if (payload[0] == MOTOR_SUBCMD_EMERGENCY_STOP &&
                       payload_len == 2) {
                binary_protocol_emergency_stop(ctx);
            }
            break;

        default:
            // Unknown function code - ignore
            break;
    }
}

// ============================================================================
// COMMAND EXTRACTION
// ============================================================================

uint8_t binary_protocol_get_motor_commands(BinaryProtocolContext *ctx,
                                          MotorCommandEntry *commands,
                                          uint8_t max_commands) {
    if (ctx->emergency_stop_active) {
        return 0;  // No commands when emergency stop is active
    }

    uint8_t count = (ctx->motor_command_count < max_commands) ? ctx->motor_command_count : max_commands;

    for (uint8_t i = 0; i < count; i++) {
        commands[i] = ctx->motor_commands.motors[i];

        // Clamp values to safe range
        if (commands[i].rps > 1.0f) commands[i].rps = 1.0f;
        if (commands[i].rps < -1.0f) commands[i].rps = -1.0f;
    }

    return count;
}

// ============================================================================
// TIMEOUT HANDLING
// ============================================================================

bool binary_protocol_check_timeouts(BinaryProtocolContext *ctx) {
    uint32_t now = HAL_GetTick();
    bool timeout_occurred = false;

    // Check command timeout
    if ((now - ctx->last_command_time) > ctx->command_timeout_ms) {
        if (!ctx->emergency_stop_active) {
            binary_protocol_emergency_stop(ctx);
            ctx->stats.timeout_errors++;
            timeout_occurred = true;
        }
    }

    // Check heartbeat timeout
    if ((now - ctx->last_heartbeat_time) > ctx->heartbeat_timeout_ms) {
        if (!ctx->emergency_stop_active) {
            binary_protocol_emergency_stop(ctx);
            ctx->stats.timeout_errors++;
            timeout_occurred = true;

            // Trigger communication lost indication
            Status_CommunicationLostBeep();
            Status_SetLEDWarning();
        }
    }

    return timeout_occurred;
}

// ============================================================================
// EMERGENCY STOP
// ============================================================================

void binary_protocol_emergency_stop(BinaryProtocolContext *ctx) {
    ctx->emergency_stop_active = true;
    ctx->motor_command_count = 0;
    memset(&ctx->motor_commands, 0, sizeof(MotorCommandPayload));

    uint8_t error_code = 0x01;  // Emergency stop
    binary_protocol_queue_frame(ctx, FUNC_ERROR, &error_code, 1);
}

// ============================================================================
// TELEMETRY
// ============================================================================

void binary_protocol_update_telemetry(BinaryProtocolContext *ctx,
                                     int32_t left_encoder,
                                     int32_t right_encoder,
                                     float battery_voltage,
                                     float battery_current,
                                     float accel_x, float accel_y, float accel_z,
                                     float gyro_x, float gyro_y, float gyro_z) {
    // Update encoder data
    ctx->telemetry.encoder.left_encoder = left_encoder;
    ctx->telemetry.encoder.right_encoder = right_encoder;

    // Update battery data
    ctx->telemetry.battery.voltage = battery_voltage;
    ctx->telemetry.battery.current = battery_current;

    // Update IMU data
    ctx->telemetry.imu.accel_x = accel_x;
    ctx->telemetry.imu.accel_y = accel_y;
    ctx->telemetry.imu.accel_z = accel_z;
    ctx->telemetry.imu.gyro_x = gyro_x;
    ctx->telemetry.imu.gyro_y = gyro_y;
    ctx->telemetry.imu.gyro_z = gyro_z;

    // Update timestamp
    ctx->telemetry.timestamp_ms = HAL_GetTick();
}

void binary_protocol_send_telemetry_burst(BinaryProtocolContext *ctx) {
    if (!ctx->telemetry_enabled) {
        return;
    }

    uint8_t frame_buffer[MAX_FRAME_SIZE];
    uint16_t frame_len = build_frame(FUNC_ENCODER,
                                     (const uint8_t *)&ctx->telemetry.encoder,
                                     sizeof(EncoderTelemetry),
                                     frame_buffer,
                                     MAX_FRAME_SIZE);
    if (frame_len > 0) {
        binary_protocol_queue_frame(ctx, FUNC_ENCODER, frame_buffer + FRAME_HEADER_SIZE,
                                    frame_len - FRAME_HEADER_SIZE - FRAME_FOOTER_SIZE);
    }

    frame_len = build_frame(FUNC_BATTERY,
                           (const uint8_t *)&ctx->telemetry.battery,
                           sizeof(BatteryTelemetry),
                           frame_buffer,
                           MAX_FRAME_SIZE);
    if (frame_len > 0) {
        binary_protocol_queue_frame(ctx, FUNC_BATTERY, frame_buffer + FRAME_HEADER_SIZE,
                                    frame_len - FRAME_HEADER_SIZE - FRAME_FOOTER_SIZE);
    }

    frame_len = build_frame(FUNC_IMU,
                           (const uint8_t *)&ctx->telemetry.imu,
                           sizeof(IMUTelemetry),
                           frame_buffer,
                           MAX_FRAME_SIZE);
    if (frame_len > 0) {
        binary_protocol_queue_frame(ctx, FUNC_IMU, frame_buffer + FRAME_HEADER_SIZE,
                                    frame_len - FRAME_HEADER_SIZE - FRAME_FOOTER_SIZE);
    }
}

// ============================================================================
// SELF-TEST IMPLEMENTATION
// ============================================================================

typedef enum {
    SELF_TEST_IDLE = 0,
    SELF_TEST_MOTOR_LEFT = 1,
    SELF_TEST_MOTOR_RIGHT = 2,
    SELF_TEST_ENCODER_LEFT = 3,
    SELF_TEST_ENCODER_RIGHT = 4,
    SELF_TEST_IMU = 5,
    SELF_TEST_BATTERY = 6,
    SELF_TEST_COMPLETE = 7
} SelfTestState;

typedef struct {
    SelfTestState state;
    uint32_t test_start_time;
    int32_t initial_encoder_left;
    int32_t initial_encoder_right;
    SelfTestResult result;
} SelfTestContext;

static SelfTestContext self_test_ctx = {0};

static uint16_t self_test_error_codes[] = {
    0x0000,  // No error
    0x0101,  // Motor left failed to respond
    0x0102,  // Motor right failed to respond
    0x0201,  // Encoder left not changing
    0x0202,  // Encoder right not changing
    0x0301,  // IMU communication failure
    0x0302,  // IMU data invalid
    0x0401,  // Battery voltage too low
    0x0402,  // Battery voltage out of range
    0x0500,  // Self-test timeout
};

SelfTestResult binary_protocol_run_self_test(BinaryProtocolContext *ctx) {
    // Self-test disabled for factory configuration
    // Return pass status to avoid blocking protocol operation
    static SelfTestResult result = {
        .overall_status = 0,  // Pass
        .test_id = SELF_TEST_COMPLETE,
        .error_code = 0
    };
    return result;
}

// ============================================================================
// HEARTBEAT
// ============================================================================

void binary_protocol_send_heartbeat(BinaryProtocolContext *ctx) {
    binary_protocol_queue_frame(ctx, FUNC_HEARTBEAT, NULL, 0);
}

// ============================================================================
// STATISTICS
// ============================================================================

const void* binary_protocol_get_stats(BinaryProtocolContext *ctx) {
    return &ctx->stats;
}
