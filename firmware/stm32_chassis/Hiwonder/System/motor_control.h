/**
 * @file motor_control.h
 * @brief Motor control wrapper for ROS2 binary protocol integration
 * 
 * This layer sits on top of Hiwonder's existing encoder_motor system
 * and provides the interface for our binary protocol parser.
 * 
 * IMPORTANT: We use Hiwonder's existing PID control system rather than
 * reimplementing it, ensuring compatibility with their hardware abstraction.
 */

#ifndef MOTOR_CONTROL_H
#define MOTOR_CONTROL_H

#include <stdint.h>
#include <stdbool.h>
#include "uart_binary_protocol_packed.h"

// Motor configuration
#define MOTOR_COUNT 4
#define CONTROL_UPDATE_FREQ_HZ 100  // 100Hz control loop
#define CONTROL_PERIOD_SEC (1.0f / CONTROL_UPDATE_FREQ_HZ)

// Motor state structure
typedef struct {
    float target_rps;           // Target velocity from ROS2
    float current_rps;          // Current measured velocity
    int32_t encoder_count;      // Current encoder count
    bool enabled;               // Motor enable state
} MotorState_t;

// Global motor state
extern MotorState_t motor_states[MOTOR_COUNT];

/**
 * @brief Initialize motor control layer
 * 
 * This function:
 * 1. Initializes motor state structures
 * 2. Ensures Hiwonder motors are properly initialized
 * 3. Configures control parameters
 * 
 * Call this from your initialization sequence.
 */
void MotorControl_Init(void);

/**
 * @brief Set target RPS for a specific motor
 * @param motor_id Motor identifier (0-3)
 * @param target_rps Target velocity in revolutions per second
 * 
 * This function is called by the binary protocol parser when
 * FUNC_MOTOR commands are received.
 */
void MotorControl_SetTargetRPS(uint8_t motor_id, float target_rps);

/**
 * @brief Get current RPS for a specific motor
 * @param motor_id Motor identifier (0-3)
 * @return Current measured velocity in revolutions per second
 */
float MotorControl_GetCurrentRPS(uint8_t motor_id);

/**
 * @brief Get encoder count for a specific motor
 * @param motor_id Motor identifier (0-3)
 * @return Current encoder count
 */
int32_t MotorControl_GetEncoderCount(uint8_t motor_id);

/**
 * @brief Update motor control loop
 * 
 * This function should be called at 100Hz (10ms period) from:
 * - A hardware timer interrupt, OR
 * - A FreeRTOS task, OR
 * - The main loop with precise timing
 * 
 * It performs:
 * 1. Encoder reading via Hiwonder's encoder_update()
 * 2. PID control via Hiwonder's encoder_motor_control()
 * 3. State updates for telemetry
 * 
 * @param period Time since last update in seconds
 */
void MotorControl_Update(float period);

/**
 * @brief Emergency stop all motors
 * 
 * Immediately sets all target RPS to 0 and calls the update function
 * to bring motors to a halt using PID control.
 */
void MotorControl_EmergencyStop(void);

/**
 * @brief Enable/disable specific motor
 * @param motor_id Motor identifier (0-3)
 * @param enabled Enable state
 */
void MotorControl_SetEnable(uint8_t motor_id, bool enabled);

/**
 * @brief Get motor enable state
 * @param motor_id Motor identifier (0-3)
 * @return Enable state
 */
bool MotorControl_GetEnable(uint8_t motor_id);

#endif // MOTOR_CONTROL_H
