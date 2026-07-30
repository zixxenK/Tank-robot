/**
 * @file uart_binary_protocol.c
 * @brief Binary UART protocol handler implementation
 */

#include "uart_binary_protocol.h"
#include <string.h>
#include <stdio.h>

// CRC-8-CCITT Lookup Table
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

// CRC-8-CCITT Calculation
static uint8_t crc8_ccitt(const uint8_t *data, uint16_t len) {
    uint8_t crc = 0x00;
    for (uint16_t i = 0; i < len; i++) {
        crc = CRC8_TABLE[crc ^ data[i]];
    }
    return crc;
}

// Build frame for transmission
static uint16_t build_frame(uint8_t func, const uint8_t *payload, uint8_t payload_len, uint8_t *output) {
    uint16_t index = 0;
    
    // Header
    output[index++] = SYNC_BYTE_1;
    output[index++] = SYNC_BYTE_2;
    output[index++] = func;
    output[index++] = payload_len;
    
    // Payload
    if (payload && payload_len > 0) {
        memcpy(&output[index], payload, payload_len);
        index += payload_len;
    }
    
    // CRC (calculated over function code + length + payload)
    uint8_t crc_data[payload_len + 2];
    crc_data[0] = func;
    crc_data[1] = payload_len;
    if (payload && payload_len > 0) {
        memcpy(&crc_data[2], payload, payload_len);
    }
    output[index++] = crc8_ccitt(crc_data, payload_len + 2);
    
    return index;
}

// Initialize protocol handler
void binary_protocol_init(BinaryProtocolContext *ctx, 
                          UART_HandleTypeDef *huart,
                          DMA_HandleTypeDef *hdma_rx,
                          DMA_HandleTypeDef *hdma_tx,
                          uint32_t command_timeout_ms) {
    memset(ctx, 0, sizeof(BinaryProtocolContext));
    
    ctx->rx_state = FRAME_STATE_SYNC1;
    ctx->uart_handle = huart;
    ctx->rx_dma_handle = hdma_rx;
    ctx->tx_dma_handle = hdma_tx;
    ctx->command_timeout_ms = command_timeout_ms;
    ctx->telemetry_interval_ms = 100; // Default 100ms
    ctx->last_command_time = HAL_GetTick();
    
    // Start DMA reception if handles provided
    if (huart && hdma_rx) {
        HAL_UART_Receive_DMA(huart, ctx->rx_buffer, RX_BUFFER_SIZE);
    }
}

// Process single byte
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
                ctx->rx_state = FRAME_STATE_SYNC1;
                if (byte == SYNC_BYTE_1) {
                    ctx->frame_buffer[0] = byte;
                    ctx->frame_pos = 1;
                    ctx->rx_state = FRAME_STATE_SYNC2;
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
            
            if (ctx->expected_payload_len == 0) {
                ctx->rx_state = FRAME_STATE_CRC;
            } else {
                ctx->rx_state = FRAME_STATE_PAYLOAD;
            }
            break;
            
        case FRAME_STATE_PAYLOAD:
            ctx->frame_buffer[ctx->frame_pos++] = byte;
            
            if (ctx->frame_pos >= FRAME_HEADER_SIZE + ctx->expected_payload_len) {
                ctx->rx_state = FRAME_STATE_CRC;
            }
            
            // Prevent buffer overflow
            if (ctx->frame_pos >= MAX_FRAME_SIZE) {
                ctx->rx_state = FRAME_STATE_SYNC1;
                ctx->stats.invalid_frames++;
            }
            break;
            
        case FRAME_STATE_CRC:
            ctx->frame_buffer[ctx->frame_pos++] = byte;
            
            // Validate frame
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

// Process buffer of bytes (for DMA)
void binary_protocol_process_buffer(BinaryProtocolContext *ctx, uint8_t *data, uint16_t len) {
    for (uint16_t i = 0; i < len; i++) {
        binary_protocol_process_byte(ctx, data[i]);
    }
}

// Forward declaration
static void binary_protocol_process_frame(BinaryProtocolContext *ctx, uint8_t func, uint8_t *payload, uint8_t payload_len);

// Process complete frame
void binary_protocol_process_frame(BinaryProtocolContext *ctx, uint8_t func, uint8_t *payload, uint8_t payload_len) {
    ctx->last_command_time = HAL_GetTick();
    
    switch (func) {
        case FUNC_HEARTBEAT:
            binary_protocol_send_heartbeat(ctx);
            break;
            
        case FUNC_MOTOR:
            if (payload_len >= 2) {
                uint8_t subcmd = payload[0];
                uint8_t motor_count = payload[1];
                
                if (subcmd == MOTOR_SUBCMD_SET_SPEED && payload_len >= 2 + motor_count * 5) {
                    // Parse motor commands: motor_id (1 byte) + rps (4 bytes float)
                    ctx->motor_command_count = 0;
                    for (uint8_t i = 0; i < motor_count && i < 8; i++) {
                        uint8_t motor_id = payload[2 + i * 5];
                        float rps;
                        memcpy(&rps, &payload[2 + i * 5 + 1], sizeof(float));
                        
                        // Clamp to valid range
                        if (rps > 1.0f) rps = 1.0f;
                        if (rps < -1.0f) rps = -1.0f;
                        
                        ctx->motor_commands[ctx->motor_command_count].motor_id = motor_id;
                        ctx->motor_commands[ctx->motor_command_count].rps = rps;
                        ctx->motor_command_count++;
                    }
                } else if (subcmd == MOTOR_SUBCMD_EMERGENCY_STOP) {
                    // Emergency stop - zero all motors
                    ctx->motor_command_count = 0;
                }
            }
            break;
            
        default:
            // Unknown function code
            break;
    }
}

// Periodic task
void binary_protocol_periodic_task(BinaryProtocolContext *ctx) {
    uint32_t now = HAL_GetTick();
    
    // Check for command timeout
    if (binary_protocol_check_timeout(ctx)) {
        // Timeout occurred - zero motor commands
        ctx->motor_command_count = 0;
        ctx->stats.timeouts++;
    }
    
    // Send periodic telemetry
    if (now - ctx->last_telemetry_time >= ctx->telemetry_interval_ms) {
        ctx->last_telemetry_time = now;
        // Telemetry is sent by dedicated functions when data is available
    }
}

// Send heartbeat
void binary_protocol_send_heartbeat(BinaryProtocolContext *ctx) {
    uint8_t frame[MAX_FRAME_SIZE];
    uint16_t frame_len = build_frame(FUNC_HEARTBEAT, NULL, 0, frame);
    
    if (ctx->uart_handle) {
        HAL_UART_Transmit(ctx->uart_handle, frame, frame_len, 100);
    }
}

// Send encoder telemetry
void binary_protocol_send_encoder_telemetry(BinaryProtocolContext *ctx, 
                                            int32_t left_encoder, 
                                            int32_t right_encoder) {
    if (!ctx->encoder_telemetry_enabled) return;
    
    uint8_t payload[8];
    memcpy(&payload[0], &left_encoder, sizeof(int32_t));
    memcpy(&payload[4], &right_encoder, sizeof(int32_t));
    
    uint8_t frame[MAX_FRAME_SIZE];
    uint16_t frame_len = build_frame(FUNC_ENCODER, payload, 8, frame);
    
    if (ctx->uart_handle) {
        HAL_UART_Transmit(ctx->uart_handle, frame, frame_len, 100);
    }
}

// Send battery telemetry
void binary_protocol_send_battery_telemetry(BinaryProtocolContext *ctx,
                                            float voltage,
                                            float current) {
    if (!ctx->battery_telemetry_enabled) return;
    
    uint8_t payload[8];
    memcpy(&payload[0], &voltage, sizeof(float));
    memcpy(&payload[4], &current, sizeof(float));
    
    uint8_t frame[MAX_FRAME_SIZE];
    uint16_t frame_len = build_frame(FUNC_BATTERY, payload, 8, frame);
    
    if (ctx->uart_handle) {
        HAL_UART_Transmit(ctx->uart_handle, frame, frame_len, 100);
    }
}

// Send IMU telemetry
void binary_protocol_send_imu_telemetry(BinaryProtocolContext *ctx,
                                       float accel_x, float accel_y, float accel_z,
                                       float gyro_x, float gyro_y, float gyro_z) {
    if (!ctx->imu_telemetry_enabled) return;
    
    uint8_t payload[24];
    memcpy(&payload[0], &accel_x, sizeof(float));
    memcpy(&payload[4], &accel_y, sizeof(float));
    memcpy(&payload[8], &accel_z, sizeof(float));
    memcpy(&payload[12], &gyro_x, sizeof(float));
    memcpy(&payload[16], &gyro_y, sizeof(float));
    memcpy(&payload[20], &gyro_z, sizeof(float));
    
    uint8_t frame[MAX_FRAME_SIZE];
    uint16_t frame_len = build_frame(FUNC_IMU, payload, 24, frame);
    
    if (ctx->uart_handle) {
        HAL_UART_Transmit(ctx->uart_handle, frame, frame_len, 100);
    }
}

// Send error
void binary_protocol_send_error(BinaryProtocolContext *ctx, uint8_t error_code) {
    uint8_t frame[MAX_FRAME_SIZE];
    uint16_t frame_len = build_frame(FUNC_ERROR, &error_code, 1, frame);
    
    if (ctx->uart_handle) {
        HAL_UART_Transmit(ctx->uart_handle, frame, frame_len, 100);
    }
}

// Get motor commands
uint8_t binary_protocol_get_motor_commands(BinaryProtocolContext *ctx,
                                          MotorCommand *commands,
                                          uint8_t max_commands) {
    uint8_t count = ctx->motor_command_count;
    if (count > max_commands) count = max_commands;
    
    for (uint8_t i = 0; i < count; i++) {
        commands[i] = ctx->motor_commands[i];
    }
    
    return count;
}

// Check timeout
bool binary_protocol_check_timeout(BinaryProtocolContext *ctx) {
    uint32_t now = HAL_GetTick();
    return (now - ctx->last_command_time) > ctx->command_timeout_ms;
}

// Get statistics
const ProtocolStats* binary_protocol_get_stats(BinaryProtocolContext *ctx) {
    return &ctx->stats;
}

// Reset statistics
void binary_protocol_reset_stats(BinaryProtocolContext *ctx) {
    memset(&ctx->stats, 0, sizeof(ProtocolStats));
}

// Enable/disable encoder telemetry
void binary_protocol_set_encoder_telemetry(BinaryProtocolContext *ctx, bool enabled) {
    ctx->encoder_telemetry_enabled = enabled;
}

// Enable/disable battery telemetry
void binary_protocol_set_battery_telemetry(BinaryProtocolContext *ctx, bool enabled) {
    ctx->battery_telemetry_enabled = enabled;
}

// Enable/disable IMU telemetry
void binary_protocol_set_imu_telemetry(BinaryProtocolContext *ctx, bool enabled) {
    ctx->imu_telemetry_enabled = enabled;
}

// Set telemetry interval
void binary_protocol_set_telemetry_interval(BinaryProtocolContext *ctx, uint32_t interval_ms) {
    ctx->telemetry_interval_ms = interval_ms;
}
