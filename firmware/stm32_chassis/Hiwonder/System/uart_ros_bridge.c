/**
 * @file uart_ros_bridge.c
 * @brief ROS protocol compatibility layer for Hiwonder STM32 firmware
 * 
 * This module provides a bridge between ROS serial bridge ASCII protocol
 * and the Hiwonder chassis control system.
 * 
 * ROS Protocol (from stm32_serial_bridge.py):
 *   Command format: <motor_id,direction,speed>\n
 *   motor_id: 0=left, 1=right
 *   direction: 0=reverse, 1=forward
 *   speed: 0-255 (PWM duty cycle)
 * 
 * Hiwonder Protocol (from app.c):
 *   Uses chassis->set_velocity(chassis, x_speed, y_speed, angular_speed)
 *   x_speed: linear velocity in mm/s
 *   y_speed: lateral velocity (usually 0 for tank)
 *   angular_speed: rotation speed in rad/s
 */

#include "uart_ros_bridge.h"
#include "chassis.h"
#include "usart.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

// External chassis object (from Hiwonder system)
extern ChassisObjectTypeDef *chassis;

// ROS command buffer
#define ROS_CMD_BUFFER_SIZE 64
static char ros_cmd_buffer[ROS_CMD_BUFFER_SIZE];
static uint16_t ros_cmd_index = 0;

// Motor state tracking
typedef struct {
    float left_speed;   // -1.0 to 1.0
    float right_speed;  // -1.0 to 1.0
    uint32_t last_update_time;
} ROSMotorState;

static ROSMotorState motor_state = {0, 0, 0};

// Timeout configuration (ms)
#define ROS_CMD_TIMEOUT_MS 200
#define HEARTBEAT_INTERVAL_MS 100

/**
 * @brief Initialize ROS UART bridge
 */
void uart_ros_bridge_init(void) {
    memset(ros_cmd_buffer, 0, ROS_CMD_BUFFER_SIZE);
    ros_cmd_index = 0;
    motor_state.left_speed = 0.0f;
    motor_state.right_speed = 0.0f;
    motor_state.last_update_time = HAL_GetTick();
}

/**
 * @brief Process incoming UART byte for ROS command parsing
 * @param byte Incoming UART byte
 */
void uart_ros_bridge_process_byte(uint8_t byte) {
    // Check for buffer overflow
    if (ros_cmd_index >= ROS_CMD_BUFFER_SIZE - 1) {
        ros_cmd_index = 0; // Reset buffer
    }
    
    // Store byte
    ros_cmd_buffer[ros_cmd_index++] = (char)byte;
    
    // Check for command termination (newline)
    if (byte == '\n' || byte == '\r') {
        ros_cmd_buffer[ros_cmd_index - 1] = '\0'; // Null-terminate
        uart_ros_bridge_parse_command(ros_cmd_buffer);
        ros_cmd_index = 0; // Reset for next command
    }
}

/**
 * @brief Parse and execute ROS command
 * @param cmd Null-terminated command string
 */
void uart_ros_bridge_parse_command(const char* cmd) {
    // Check for heartbeat ping
    if (strcmp(cmd, "PING") == 0 || strcmp(cmd, "ping") == 0) {
        uart_ros_bridge_send_heartbeat();
        return;
    }
    
    // Check for emergency stop
    if (strcmp(cmd, "STOP") == 0 || strcmp(cmd, "stop") == 0) {
        chassis->stop(chassis);
        motor_state.left_speed = 0.0f;
        motor_state.right_speed = 0.0f;
        motor_state.last_update_time = HAL_GetTick();
        uart_ros_bridge_send_ack("STOP");
        return;
    }
    
    // Parse motor command: <motor_id,direction,speed>
    int motor_id, direction, speed;
    if (sscanf(cmd, "<%d,%d,%d>", &motor_id, &direction, &speed) == 3) {
        uart_ros_bridge_execute_motor_command(motor_id, direction, speed);
    }
}

/**
 * @brief Execute motor command from ROS bridge
 * @param motor_id 0=left, 1=right
 * @param direction 0=reverse, 1=forward
 * @param speed 0-255 (PWM value)
 */
void uart_ros_bridge_execute_motor_command(int motor_id, int direction, int speed) {
    // Clamp speed to valid range
    if (speed < 0) speed = 0;
    if (speed > 255) speed = 255;
    
    // Convert to normalized speed (-1.0 to 1.0)
    float normalized_speed = (float)speed / 255.0f;
    
    // Apply direction
    if (direction == 0) {
        normalized_speed = -normalized_speed; // Reverse
    }
    
    // Update motor state
    if (motor_id == 0) {
        motor_state.left_speed = normalized_speed;
    } else if (motor_id == 1) {
        motor_state.right_speed = normalized_speed;
    }
    
    motor_state.last_update_time = HAL_GetTick();
    
    // Apply to chassis
    uart_ros_bridge_apply_to_chassis();
    
    // Send acknowledgment
    char ack[32];
    snprintf(ack, sizeof(ack), "ACK M%d D%d S%d", motor_id, direction, speed);
    uart_ros_bridge_send_ack(ack);
}

/**
 * @brief Apply current motor state to Hiwonder chassis
 */
void uart_ros_bridge_apply_to_chassis(void) {
    // Convert normalized speeds to chassis velocities
    // Hiwonder uses mm/s for linear velocity
    const float MAX_LINEAR_SPEED = 500.0f; // mm/s (adjust based on your robot)
    
    float left_linear = motor_state.left_speed * MAX_LINEAR_SPEED;
    float right_linear = motor_state.right_speed * MAX_LINEAR_SPEED;
    
    // Calculate differential drive velocities
    float x_speed = (left_linear + right_linear) / 2.0f;
    float angular_speed = (right_linear - left_linear) / 300.0f; // 300mm track width
    
    // Apply to chassis
    chassis->set_velocity(chassis, x_speed, 0.0f, angular_speed);
}

/**
 * @brief Check for command timeout and stop motors if needed
 * @return 1 if timeout occurred, 0 otherwise
 */
uint8_t uart_ros_bridge_check_timeout(void) {
    uint32_t current_time = HAL_GetTick();
    if (current_time - motor_state.last_update_time > ROS_CMD_TIMEOUT_MS) {
        // Timeout - stop motors
        if (motor_state.left_speed != 0.0f || motor_state.right_speed != 0.0f) {
            chassis->stop(chassis);
            motor_state.left_speed = 0.0f;
            motor_state.right_speed = 0.0f;
            return 1;
        }
    }
    return 0;
}

/**
 * @brief Send heartbeat response
 */
void uart_ros_bridge_send_heartbeat(void) {
    const char* heartbeat = "HEARTBEAT\n";
    // Send via USART2 (adjust UART handle as needed)
    // HAL_UART_Transmit(&huart2, (uint8_t*)heartbeat, strlen(heartbeat), 100);
}

/**
 * @brief Send acknowledgment message
 * @param msg Acknowledgment message
 */
void uart_ros_bridge_send_ack(const char* msg) {
    char ack_buffer[64];
    snprintf(ack_buffer, sizeof(ack_buffer), "%s\n", msg);
    // Send via USART2
    // HAL_UART_Transmit(&huart2, (uint8_t*)ack_buffer, strlen(ack_buffer), 100);
}

/**
 * @brief Send encoder telemetry (if available)
 * @param left_encoder Left encoder count
 * @param right_encoder Right encoder count
 */
void uart_ros_bridge_send_encoder_telemetry(int32_t left_encoder, int32_t right_encoder) {
    char telemetry_buffer[64];
    snprintf(telemetry_buffer, sizeof(telemetry_buffer), "ENC:%d,%d\n", 
             left_encoder, right_encoder);
    // Send via USART2
    // HAL_UART_Transmit(&huart2, (uint8_t*)telemetry_buffer, strlen(telemetry_buffer), 100);
}

/**
 * @brief Periodic task for ROS bridge maintenance
 * Call this from your main loop or timer callback
 */
void uart_ros_bridge_periodic_task(void) {
    static uint32_t last_heartbeat_time = 0;
    uint32_t current_time = HAL_GetTick();
    
    // Check for command timeout
    if (uart_ros_bridge_check_timeout()) {
        // Timeout occurred
    }
    
    // Send periodic heartbeat
    if (current_time - last_heartbeat_time > HEARTBEAT_INTERVAL_MS) {
        uart_ros_bridge_send_heartbeat();
        last_heartbeat_time = current_time;
    }
}
