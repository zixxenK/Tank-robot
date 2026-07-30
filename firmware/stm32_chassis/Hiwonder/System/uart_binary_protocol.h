/**
 * @file uart_binary_protocol.h
 * @brief Binary UART protocol handler for STM32-ROS2 communication
 * 
 * Industrial-grade binary protocol with:
 * - Frame synchronization (0xAA 0x55)
 * - CRC-8-CCITT validation
 * - Non-blocking DMA-based communication
 * - Command timeout safety
 * - Telemetry reporting
 */

#ifndef UART_BINARY_PROTOCOL_H
#define UART_BINARY_PROTOCOL_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <stdbool.h>
#include "stm32f4xx_hal.h"

// Protocol Constants
#define SYNC_BYTE_1              0xAA
#define SYNC_BYTE_2              0x55
#define FRAME_HEADER_SIZE        4  // SYNC_1, SYNC_2, FUNC, LEN
#define FRAME_FOOTER_SIZE        1  // CRC
#define MAX_FRAME_SIZE           256
#define RX_BUFFER_SIZE           512
#define TX_BUFFER_SIZE           512

// Function Codes
typedef enum {
    FUNC_SYS              = 0x00,
    FUNC_MOTOR            = 0x03,
    FUNC_ENCODER          = 0x10,
    FUNC_BATTERY          = 0x11,
    FUNC_IMU              = 0x12,
    FUNC_HEARTBEAT        = 0xF0,
    FUNC_ACK              = 0xF1,
    FUNC_ERROR            = 0xFF
} FunctionCode;

// Motor Sub-commands
typedef enum {
    MOTOR_SUBCMD_SET_SPEED       = 0x01,
    MOTOR_SUBCMD_EMERGENCY_STOP = 0x02
} MotorSubCommand;

// Frame States
typedef enum {
    FRAME_STATE_SYNC1,
    FRAME_STATE_SYNC2,
    FRAME_STATE_FUNC,
    FRAME_STATE_LEN,
    FRAME_STATE_PAYLOAD,
    FRAME_STATE_CRC
} FrameState;

// Motor Command Structure
typedef struct {
    uint8_t motor_id;
    float rps;  // Normalized velocity (-1.0 to 1.0)
} MotorCommand;

// Protocol Statistics
typedef struct {
    uint32_t valid_frames;
    uint32_t invalid_frames;
    uint32_t crc_errors;
    uint32_t buffer_overflows;
    uint32_t timeouts;
} ProtocolStats;

// Protocol Context
typedef struct {
    // RX State
    FrameState rx_state;
    uint8_t rx_buffer[RX_BUFFER_SIZE];
    uint16_t rx_write_pos;
    uint16_t rx_read_pos;
    uint8_t frame_buffer[MAX_FRAME_SIZE];
    uint16_t frame_pos;
    uint8_t expected_payload_len;
    
    // TX State
    uint8_t tx_buffer[TX_BUFFER_SIZE];
    uint16_t tx_write_pos;
    uint16_t tx_read_pos;
    bool tx_busy;
    
    // Command Processing
    MotorCommand motor_commands[8];
    uint8_t motor_command_count;
    uint32_t last_command_time;
    uint32_t command_timeout_ms;
    
    // Telemetry Enable
    bool encoder_telemetry_enabled;
    bool battery_telemetry_enabled;
    bool imu_telemetry_enabled;
    uint32_t telemetry_interval_ms;
    uint32_t last_telemetry_time;
    
    // Statistics
    ProtocolStats stats;
    
    // UART Handle (set during init)
    UART_HandleTypeDef *uart_handle;
    
    // DMA Handles (set during init)
    DMA_HandleTypeDef *rx_dma_handle;
    DMA_HandleTypeDef *tx_dma_handle;
    
} BinaryProtocolContext;

// Function Prototypes

/**
 * @brief Initialize binary protocol handler
 * @param ctx Protocol context
 * @param huart UART handle
 * @param hdma_rx RX DMA handle
 * @param hdma_tx TX DMA handle
 * @param command_timeout_ms Command timeout in milliseconds
 */
void binary_protocol_init(BinaryProtocolContext *ctx, 
                          UART_HandleTypeDef *huart,
                          DMA_HandleTypeDef *hdma_rx,
                          DMA_HandleTypeDef *hdma_tx,
                          uint32_t command_timeout_ms);

/**
 * @brief Process incoming byte (call from UART RX callback or polling)
 * @param ctx Protocol context
 * @param byte Received byte
 */
void binary_protocol_process_byte(BinaryProtocolContext *ctx, uint8_t byte);

/**
 * @brief Process buffer of bytes (for DMA reception)
 * @param ctx Protocol context
 * @param data Pointer to data buffer
 * @param len Number of bytes to process
 */
void binary_protocol_process_buffer(BinaryProtocolContext *ctx, uint8_t *data, uint16_t len);

/**
 * @brief Periodic task (call from main loop or timer)
 * @param ctx Protocol context
 */
void binary_protocol_periodic_task(BinaryProtocolContext *ctx);

/**
 * @brief Send heartbeat response
 * @param ctx Protocol context
 */
void binary_protocol_send_heartbeat(BinaryProtocolContext *ctx);

/**
 * @brief Send encoder telemetry
 * @param ctx Protocol context
 * @param left_encoder Left encoder count
 * @param right_encoder Right encoder count
 */
void binary_protocol_send_encoder_telemetry(BinaryProtocolContext *ctx, 
                                            int32_t left_encoder, 
                                            int32_t right_encoder);

/**
 * @brief Send battery telemetry
 * @param ctx Protocol context
 * @param voltage Battery voltage in volts
 * @param current Battery current in amps
 */
void binary_protocol_send_battery_telemetry(BinaryProtocolContext *ctx,
                                            float voltage,
                                            float current);

/**
 * @brief Send IMU telemetry
 * @param ctx Protocol context
 * @param accel_x, accel_y, accel_z Accelerometer data (m/s²)
 * @param gyro_x, gyro_y, gyro_z Gyroscope data (rad/s)
 */
void binary_protocol_send_imu_telemetry(BinaryProtocolContext *ctx,
                                       float accel_x, float accel_y, float accel_z,
                                       float gyro_x, float gyro_y, float gyro_z);

/**
 * @brief Send error message
 * @param ctx Protocol context
 * @param error_code Error code
 */
void binary_protocol_send_error(BinaryProtocolContext *ctx, uint8_t error_code);

/**
 * @brief Get motor commands for processing by chassis control
 * @param ctx Protocol context
 * @param commands Output array for motor commands
 * @param max_commands Maximum number of commands to return
 * @return Number of motor commands available
 */
uint8_t binary_protocol_get_motor_commands(BinaryProtocolContext *ctx,
                                          MotorCommand *commands,
                                          uint8_t max_commands);

/**
 * @brief Check if command timeout has occurred
 * @param ctx Protocol context
 * @return true if timeout occurred, false otherwise
 */
bool binary_protocol_check_timeout(BinaryProtocolContext *ctx);

/**
 * @brief Get protocol statistics
 * @param ctx Protocol context
 * @return Pointer to statistics structure
 */
const ProtocolStats* binary_protocol_get_stats(BinaryProtocolContext *ctx);

/**
 * @brief Reset protocol statistics
 * @param ctx Protocol context
 */
void binary_protocol_reset_stats(BinaryProtocolContext *ctx);

/**
 * @brief Enable/disable encoder telemetry
 * @param ctx Protocol context
 * @param enabled true to enable, false to disable
 */
void binary_protocol_set_encoder_telemetry(BinaryProtocolContext *ctx, bool enabled);

/**
 * @brief Enable/disable battery telemetry
 * @param ctx Protocol context
 * @param enabled true to enable, false to disable
 */
void binary_protocol_set_battery_telemetry(BinaryProtocolContext *ctx, bool enabled);

/**
 * @brief Enable/disable IMU telemetry
 * @param ctx Protocol context
 * @param enabled true to enable, false to disable
 */
void binary_protocol_set_imu_telemetry(BinaryProtocolContext *ctx, bool enabled);

/**
 * @brief Set telemetry transmission interval
 * @param ctx Protocol context
 * @param interval_ms Interval in milliseconds
 */
void binary_protocol_set_telemetry_interval(BinaryProtocolContext *ctx, uint32_t interval_ms);

/**
 * @brief Process complete frame (internal function, made public for testing)
 * @param ctx Protocol context
 * @param func Function code
 * @param payload Payload data
 * @param payload_len Payload length
 */
void binary_protocol_process_frame(BinaryProtocolContext *ctx, uint8_t func, uint8_t *payload, uint8_t payload_len);

#ifdef __cplusplus
}
#endif

#endif /* UART_BINARY_PROTOCOL_H */
