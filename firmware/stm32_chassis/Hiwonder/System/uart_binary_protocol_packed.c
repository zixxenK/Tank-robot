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
#include <string.h>
#include <stdio.h>

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

static uint16_t build_frame(uint8_t func, const uint8_t *payload, uint8_t payload_len, uint8_t *output) {
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

// ============================================================================
// INITIALIZATION
// ============================================================================

void binary_protocol_init_packed(BinaryProtocolContext *ctx,
                                 UART_HandleTypeDef *huart,
                                 DMA_HandleTypeDef *hdma_rx,
                                 DMA_HandleTypeDef *hdma_tx,
                                 TIM_HandleTypeDef *htim_watchdog,
                                 uint32_t command_timeout_ms,
                                 uint32_t heartbeat_timeout_ms) {
    // Clear entire context
    memset(ctx, 0, sizeof(BinaryProtocolContext));
    
    // Store hardware handles
    ctx->uart_handle = huart;
    ctx->rx_dma_handle = hdma_rx;
    ctx->tx_dma_handle = hdma_tx;
    ctx->watchdog_timer = htim_watchdog;
    
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
    
    // Start hardware timer for timeout protection
    if (htim_watchdog) {
        HAL_TIM_Base_Start(htim_watchdog);
    }
    
    // Start DMA circular reception
    if (huart && hdma_rx) {
        // Configure DMA for circular mode
        hdma_rx->Instance->CR |= DMA_SxCR_CIRC;  // Enable circular mode
        
        // Start DMA reception
        HAL_UART_Receive_DMA(huart, (uint8_t*)ctx->rx_buffer, RX_BUFFER_SIZE);
    }
}

// ============================================================================
// DMA BUFFER PROCESSING
// ============================================================================

void binary_protocol_process_dma(BinaryProtocolContext *ctx) {
    // Calculate available data in circular buffer
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
                ctx->frame_pos = 0;
                ctx->stats.invalid_frames++;
            }
            break;
            
        case FRAME_STATE_CRC:
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
    // Update command timestamp (resets timeout)
    ctx->last_command_time = HAL_GetTick();
    
    switch (func) {
        case FUNC_HEARTBEAT:
            ctx->last_heartbeat_time = HAL_GetTick();
            binary_protocol_send_heartbeat(ctx);
            break;
            
        case FUNC_MOTOR:
            if (payload_len >= 2) {
                MotorCommandPayload *cmd = (MotorCommandPayload*)payload;
                
                if (cmd->subcmd == MOTOR_SUBCMD_SET_SPEED) {
                    // Validate motor count
                    uint8_t motor_count = (cmd->motor_count < 8) ? cmd->motor_count : 8;
                    
                    // Copy motor commands
                    ctx->motor_command_count = motor_count;
                    memcpy(&ctx->motor_commands, cmd, sizeof(MotorCommandPayload));
                    
                    // Clear emergency stop
                    ctx->emergency_stop_active = false;
                    
                } else if (cmd->subcmd == MOTOR_SUBCMD_EMERGENCY_STOP) {
                    // Emergency stop
                    binary_protocol_emergency_stop(ctx);
                }
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
    
    // Send error indication to host
    uint8_t error_code = 0x01;  // Emergency stop
    uint8_t frame[MAX_FRAME_SIZE];
    uint16_t frame_len = build_frame(FUNC_ERROR, &error_code, 1, frame);
    
    if (ctx->uart_handle && !ctx->tx_busy) {
        HAL_UART_Transmit(ctx->uart_handle, frame, frame_len, 100);
    }
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
    if (!ctx->telemetry_enabled || ctx->tx_busy) {
        return;
    }
    
    uint32_t now = HAL_GetTick();
    if ((now - ctx->last_telemetry_time) < ctx->telemetry_interval_ms) {
        return;
    }
    
    ctx->last_telemetry_time = now;
    
    // Build frame with complete telemetry
    uint8_t frame[MAX_FRAME_SIZE];
    uint16_t frame_len = build_frame(FUNC_ENCODER, 
                                     (uint8_t*)&ctx->telemetry.encoder, 
                                     sizeof(EncoderTelemetry), 
                                     frame);
    
    if (ctx->uart_handle) {
        HAL_UART_Transmit(ctx->uart_handle, frame, frame_len, 50);
    }
    
    // Send battery telemetry
    frame_len = build_frame(FUNC_BATTERY,
                          (uint8_t*)&ctx->telemetry.battery,
                          sizeof(BatteryTelemetry),
                          frame);
    
    if (ctx->uart_handle) {
        HAL_UART_Transmit(ctx->uart_handle, frame, frame_len, 50);
    }
    
    // Send IMU telemetry
    frame_len = build_frame(FUNC_IMU,
                          (uint8_t*)&ctx->telemetry.imu,
                          sizeof(IMUTelemetry),
                          frame);
    
    if (ctx->uart_handle) {
        HAL_UART_Transmit(ctx->uart_handle, frame, frame_len, 50);
    }
}

// ============================================================================
// HEARTBEAT
// ============================================================================

void binary_protocol_send_heartbeat(BinaryProtocolContext *ctx) {
    uint8_t frame[MAX_FRAME_SIZE];
    uint16_t frame_len = build_frame(FUNC_HEARTBEAT, NULL, 0, frame);
    
    if (ctx->uart_handle && !ctx->tx_busy) {
        HAL_UART_Transmit(ctx->uart_handle, frame, frame_len, 50);
    }
}

// ============================================================================
// STATISTICS
// ============================================================================

const void* binary_protocol_get_stats(BinaryProtocolContext *ctx) {
    return &ctx->stats;
}
