/**
 * @file uart_binary_protocol_packed.h
 * @brief Packed binary protocol structures for STM32-ROS2 communication
 * 
 * CRITICAL: All structs use __attribute__((packed)) to prevent ARM alignment padding
 * This ensures exact byte-level matching with Python struct.pack() format
 */

#ifndef UART_BINARY_PROTOCOL_PACKED_H
#define UART_BINARY_PROTOCOL_PACKED_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <stdbool.h>
#include <stm32f4xx_hal.h>

// Protocol Constants
#define SYNC_BYTE_1              0xAA
#define SYNC_BYTE_2              0x55
#define FRAME_HEADER_SIZE        4  // SYNC_1, SYNC_2, FUNC, LEN
#define FRAME_FOOTER_SIZE        1  // CRC
#define MAX_FRAME_SIZE           256
#define MAX_PAYLOAD_SIZE         (MAX_FRAME_SIZE - FRAME_HEADER_SIZE - FRAME_FOOTER_SIZE)
#define RX_BUFFER_SIZE           512
#define TX_FRAME_QUEUE_DEPTH     8
#define MOTOR_COMMAND_CAPACITY   4

// Function Codes
typedef enum {
    FUNC_SYS              = 0x00,
    FUNC_BUZZER           = 0x04,
    FUNC_SERVO            = 0x05,
    FUNC_MOTOR            = 0x03,
    FUNC_ENCODER          = 0x10,
    FUNC_BATTERY          = 0x11,
    FUNC_IMU              = 0x12,
    FUNC_SELF_TEST        = 0x13,
    FUNC_ULTRASONIC       = 0x14,
    FUNC_HEARTBEAT        = 0xF0,
    FUNC_ACK              = 0xF1,
    FUNC_ERROR            = 0xFF
} FunctionCode;

// Buzzer sub-commands
typedef enum {
    BUZZER_SUBCMD_SET_TONE = 0x01
} BuzzerSubCommand;

// SG90 PWM servo sub-commands
typedef enum {
    SERVO_SUBCMD_SET_PULSE = 0x01
} ServoSubCommand;

// Motor Sub-commands
typedef enum {
    MOTOR_SUBCMD_SET_SPEED       = 0x01,
    MOTOR_SUBCMD_EMERGENCY_STOP = 0x02
} MotorSubCommand;

// ============================================================================
// PACKED STRUCTURES - Must match Python struct.pack() format exactly
// ============================================================================

/**
 * @brief Motor command entry (matches Python: struct.pack('<Bf', motor_id, rps))
 * 
 * Python: struct.pack('<Bf', motor_id, rps)
 * C layout: uint8_t (1 byte) + float (4 bytes) = 5 bytes total
 * NO PADDING due to __attribute__((packed))
 */
typedef struct __attribute__((packed)) {
    uint8_t motor_id;    // Motor identifier (0=left, 1=right)
    float rps;           // Normalized velocity (-1.0 to 1.0)
} MotorCommandEntry;

/**
 * @brief Motor command payload (matches Python motor command construction)
 * 
 * Python format: [SUBCMD][COUNT][MOTOR_ID][RPS][MOTOR_ID][RPS]...
 * C layout: uint8_t + uint8_t + MotorCommandEntry[]
 */
typedef struct __attribute__((packed)) {
    uint8_t subcmd;                  // MotorSubCommand
    uint8_t motor_count;             // Number of motor commands
    MotorCommandEntry motors[MOTOR_COMMAND_CAPACITY];
} MotorCommandPayload;

/**
 * @brief SG90 command/acknowledgement payload.
 *
 * Wire format: [subcmd][channel][pulse_us LE16][duration_ms LE16]
 * Only channel 0 (J1 / PA11) is supported by the production image.
 */
typedef struct __attribute__((packed)) {
    uint8_t subcmd;
    uint8_t channel;
    uint16_t pulse_us;
    uint16_t duration_ms;
} ServoCommandPayload;

/**
 * @brief Encoder telemetry payload (matches Python: struct.pack('<ii', left, right))
 * 
 * Python: struct.pack('<ii', left_encoder, right_encoder)
 * C layout: int32_t + int32_t = 8 bytes
 */
typedef struct __attribute__((packed)) {
    int32_t left_encoder;    // Left encoder count
    int32_t right_encoder;   // Right encoder count
} EncoderTelemetry;

/**
 * @brief Battery telemetry payload (matches Python: struct.pack('<ff', voltage, current))
 * 
 * Python: struct.pack('<ff', voltage, current)
 * C layout: float + float = 8 bytes
 */
typedef struct __attribute__((packed)) {
    float voltage;           // Battery voltage (volts)
    float current;           // Battery current (amps)
} BatteryTelemetry;

/**
 * @brief IMU telemetry payload (matches Python: struct.pack('<ffffff', ...))
 * 
 * Python: struct.pack('<ffffff', accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z)
 * C layout: 6 floats = 24 bytes
 */
typedef struct __attribute__((packed)) {
    float accel_x;           // Accelerometer X (m/s²)
    float accel_y;           // Accelerometer Y (m/s²)
    float accel_z;           // Accelerometer Z (m/s²)
    float gyro_x;            // Gyroscope X (rad/s)
    float gyro_y;            // Gyroscope Y (rad/s)
    float gyro_z;            // Gyroscope Z (rad/s)
} IMUTelemetry;

/** @brief HC-SR04 echo measurement in millimetres and microseconds. */
typedef struct __attribute__((packed)) {
    uint16_t distance_mm;
    uint16_t echo_us;
    uint8_t valid;
    uint8_t reserved;
} UltrasonicTelemetry;

/**
 * @brief Complete telemetry struct for burst transmission
 * Combines all telemetry into single packed structure
 */
typedef struct __attribute__((packed)) {
    EncoderTelemetry encoder;
    BatteryTelemetry battery;
    IMUTelemetry imu;
    UltrasonicTelemetry ultrasonic;
    uint32_t timestamp_ms;    // System timestamp
} CompleteTelemetry;

/**
 * @brief Self-test result payload (matches Python: struct.pack('<BBH', status, test_id, error_code))
 * 
 * Python: struct.pack('<BBH', status, test_id, error_code)
 * C layout: uint8_t + uint8_t + uint16_t = 4 bytes
 */
typedef struct __attribute__((packed)) {
    uint8_t overall_status;   // 0=pass, 1=fail, 2=running
    uint8_t test_id;          // Current test identifier
    uint16_t error_code;      // Specific error code for failed test
} SelfTestResult;

/**
 * @brief Self-test request payload (empty for trigger)
 * Self-test is triggered by FUNC_SELF_TEST with empty payload
 */

// ============================================================================
// PARSER STATE MACHINE
// ============================================================================

typedef enum {
    FRAME_STATE_SYNC1,
    FRAME_STATE_SYNC2,
    FRAME_STATE_FUNC,
    FRAME_STATE_LEN,
    FRAME_STATE_PAYLOAD,
    FRAME_STATE_CRC
} FrameState;

typedef struct {
    uint16_t length;
    uint8_t data[MAX_FRAME_SIZE];
} ProtocolTxFrame;

typedef uint8_t (*ProtocolTransmitCallback)(uint8_t *data,
                                            uint16_t length);

// ============================================================================
// PROTOCOL CONTEXT
// ============================================================================

typedef struct {
    // RX State (DMA-backed circular buffer)
    volatile uint8_t rx_buffer[RX_BUFFER_SIZE];
    volatile uint16_t rx_write_pos;  // DMA write position
    volatile uint16_t rx_read_pos;   // Parser read position
    volatile uint16_t rx_event_pos;  // Position reported by HAL idle-DMA
    volatile bool rx_event_pending;  // Set by HAL_UARTEx_RxEventCallback
    
    // Frame Parser State
    FrameState rx_state;
    uint8_t frame_buffer[MAX_FRAME_SIZE];
    uint16_t frame_pos;
    uint8_t expected_payload_len;
    
    // TX State
    ProtocolTxFrame tx_queue[TX_FRAME_QUEUE_DEPTH];
    volatile uint8_t tx_head;
    volatile uint8_t tx_tail;
    volatile bool tx_busy;
    
    // Command Processing
    MotorCommandPayload motor_commands;
    uint8_t motor_command_count;
    uint32_t last_command_time;
    uint32_t command_timeout_ms;
    
    // Telemetry State
    CompleteTelemetry telemetry;
    bool telemetry_enabled;
    uint32_t telemetry_interval_ms;
    uint32_t last_telemetry_time;
    
    // Safety State
    bool emergency_stop_active;
    bool heartbeat_required;
    uint32_t last_heartbeat_time;
    uint32_t heartbeat_timeout_ms;
    
    // Statistics
    struct {
        uint32_t valid_frames;
        uint32_t invalid_frames;
        uint32_t crc_errors;
        uint32_t timeout_errors;
        uint32_t buffer_overruns;
        uint32_t tx_queue_overruns;
        uint32_t tx_errors;
    } stats;
    
    // Hardware Handles
    UART_HandleTypeDef *uart_handle;
    DMA_HandleTypeDef *rx_dma_handle;
    DMA_HandleTypeDef *tx_dma_handle;
    ProtocolTransmitCallback transmit_callback;
} BinaryProtocolContext;

// ============================================================================
// FUNCTION PROTOTYPES
// ============================================================================

/**
 * @brief Initialize binary protocol with DMA and hardware timer
 * @param ctx Protocol context
 * @param huart UART handle for the Rock64 link
 * @param hdma_rx UART RX DMA handle
 * @param hdma_tx UART TX DMA handle
 * @param command_timeout_ms Command timeout in milliseconds
 * @param heartbeat_timeout_ms Heartbeat timeout in milliseconds
 */
void binary_protocol_init_packed(BinaryProtocolContext *ctx,
                                 UART_HandleTypeDef *huart,
                                 DMA_HandleTypeDef *hdma_rx,
                                 DMA_HandleTypeDef *hdma_tx,
                                 uint32_t command_timeout_ms,
                                 uint32_t heartbeat_timeout_ms);

/**
 * @brief Process incoming bytes from DMA circular buffer
 * Call this from main loop or dedicated task
 * @param ctx Protocol context
 */
void binary_protocol_process_dma(BinaryProtocolContext *ctx);

/**
 * @brief Record a HAL UART idle-DMA reception event.
 * @param ctx Protocol context
 * @param position DMA write position reported by HAL
 */
void binary_protocol_rx_event(BinaryProtocolContext *ctx, uint16_t position);

void binary_protocol_process_bytes(BinaryProtocolContext *ctx,
                                   const uint8_t *data,
                                   uint16_t length);

void binary_protocol_set_transmit_callback(BinaryProtocolContext *ctx,
                                           ProtocolTransmitCallback callback);

/**
 * @brief Send heartbeat response
 * @param ctx Protocol context
 */
void binary_protocol_send_heartbeat(BinaryProtocolContext *ctx);

/**
 * @brief Send complete telemetry burst
 * @param ctx Protocol context
 */
void binary_protocol_send_telemetry_burst(BinaryProtocolContext *ctx);

/**
 * @brief Advance the transmit queue after UART DMA completion.
 * @param ctx Protocol context
 */
void binary_protocol_tx_complete(BinaryProtocolContext *ctx);

/**
 * @brief Emergency stop - zero all motors immediately
 * @param ctx Protocol context
 */
void binary_protocol_emergency_stop(BinaryProtocolContext *ctx);

/**
 * @brief Get motor commands for chassis control
 * @param ctx Protocol context
 * @param commands Output array for motor commands
 * @param max_commands Maximum number of commands
 * @return Number of motor commands
 */
uint8_t binary_protocol_get_motor_commands(BinaryProtocolContext *ctx,
                                          MotorCommandEntry *commands,
                                          uint8_t max_commands);

/**
 * @brief Update telemetry data structure
 * Call this before sending telemetry burst
 * @param ctx Protocol context
 * @param left_encoder Left encoder count
 * @param right_encoder Right encoder count
 * @param battery_voltage Battery voltage
 * @param battery_current Battery current
 * @param accel_x, accel_y, accel_z Accelerometer data
 * @param gyro_x, gyro_y, gyro_z Gyroscope data
 */
void binary_protocol_update_telemetry(BinaryProtocolContext *ctx,
                                     int32_t left_encoder,
                                     int32_t right_encoder,
                                     float battery_voltage,
                                     float battery_current,
                                     float accel_x, float accel_y, float accel_z,
                                     float gyro_x, float gyro_y, float gyro_z);

/**
 * @brief Check and handle timeouts
 * Call this periodically (e.g., every 1ms)
 * @param ctx Protocol context
 * @return true if timeout occurred, false otherwise
 */
bool binary_protocol_check_timeouts(BinaryProtocolContext *ctx);

/**
 * @brief Get protocol statistics
 * @param ctx Protocol context
 * @return Pointer to statistics structure
 */
const void* binary_protocol_get_stats(BinaryProtocolContext *ctx);

/**
 * @brief Process single byte (internal function for state machine)
 * @param ctx Protocol context
 * @param byte Incoming byte
 */
void binary_protocol_process_byte(BinaryProtocolContext *ctx, uint8_t byte);

/**
 * @brief Process complete frame (internal function)
 * @param ctx Protocol context
 * @param func Function code
 * @param payload Payload data
 * @param payload_len Payload length
 */
void binary_protocol_process_frame(BinaryProtocolContext *ctx, uint8_t func, uint8_t *payload, uint8_t payload_len);

/**
 * @brief Run comprehensive self-test sequence
 * Tests motors, encoders, IMU, battery, and communication
 * @param ctx Protocol context
 * @return Self-test result structure
 */
SelfTestResult binary_protocol_run_self_test(BinaryProtocolContext *ctx);

#ifdef __cplusplus
}
#endif

#endif /* UART_BINARY_PROTOCOL_PACKED_H */
