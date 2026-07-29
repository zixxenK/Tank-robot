/**
 * @file uart_ros_cmd.c
 * @brief Simple ROS command handler for Hiwonder firmware
 * 
 * Integrates ROS ASCII protocol with existing Hiwonder chassis control
 * Command format: <motor_id,direction,speed>\n
 */

#include "main.h"
#include "usart.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

// External chassis object from Hiwonder system
extern ChassisObjectTypeDef *chassis;

// Command buffer
#define CMD_BUFFER_SIZE 64
static char cmd_buffer[CMD_BUFFER_SIZE];
static uint16_t cmd_index = 0;

// Motor command structure
typedef struct {
    int motor_id;
    int direction;
    int speed;
} ROSMotorCmd;

/**
 * @brief Initialize ROS command handler
 */
void uart_ros_cmd_init(void) {
    memset(cmd_buffer, 0, CMD_BUFFER_SIZE);
    cmd_index = 0;
}

/**
 * @brief Process incoming UART byte for ROS commands
 * Call this from your UART RX interrupt or polling loop
 */
void uart_ros_process_byte(uint8_t byte) {
    // Check for command termination
    if (byte == '\n' || byte == '\r') {
        if (cmd_index > 0) {
            cmd_buffer[cmd_index] = '\0';
            uart_ros_execute_command(cmd_buffer);
            cmd_index = 0;
        }
        return;
    }
    
    // Store byte if buffer not full
    if (cmd_index < CMD_BUFFER_SIZE - 1) {
        cmd_buffer[cmd_index++] = (char)byte;
    } else {
        cmd_index = 0; // Reset on overflow
    }
}

/**
 * @brief Parse and execute ROS command
 */
void uart_ros_execute_command(const char* cmd) {
    // Check for simple commands
    if (strcmp(cmd, "PING") == 0 || strcmp(cmd, "ping") == 0) {
        // Send heartbeat response via USART2
        const char* response = "HEARTBEAT\n";
        HAL_UART_Transmit(&huart2, (uint8_t*)response, strlen(response), 100);
        return;
    }
    
    if (strcmp(cmd, "STOP") == 0 || strcmp(cmd, "stop") == 0) {
        chassis->stop(chassis);
        const char* response = "ACK STOP\n";
        HAL_UART_Transmit(&huart2, (uint8_t*)response, strlen(response), 100);
        return;
    }
    
    // Parse motor command: <motor_id,direction,speed>
    int motor_id, direction, speed;
    if (sscanf(cmd, "<%d,%d,%d>", &motor_id, &direction, &speed) == 3) {
        // Clamp values
        if (motor_id < 0) motor_id = 0;
        if (motor_id > 1) motor_id = 1;
        if (direction < 0) direction = 0;
        if (direction > 1) direction = 1;
        if (speed < 0) speed = 0;
        if (speed > 255) speed = 255;
        
        // Convert to chassis velocity
        float motor_speed = (float)speed / 255.0f * 500.0f; // Scale to 500 mm/s max
        
        if (direction == 0) {
            motor_speed = -motor_speed; // Reverse
        }
        
        // Apply to chassis
        if (motor_id == 0) {
            // Left motor
            chassis->set_velocity(chassis, motor_speed, 0, 0);
        } else {
            // Right motor  
            chassis->set_velocity(chassis, 0, motor_speed, 0);
        }
        
        // Send acknowledgment
        char ack[32];
        snprintf(ack, sizeof(ack), "ACK M%d D%d S%d\n", motor_id, direction, speed);
        HAL_UART_Transmit(&huart2, (uint8_t*)ack, strlen(ack), 100);
    }
}

/**
 * @brief Call this from your main loop or UART RX handler
 * Example integration in usart.c or main.c:
 * 
 * In UART RX callback:
 * void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart) {
 *     if (huart->Instance == USART2) {
 *         uint8_t byte = rx_buffer[0];
 *         uart_ros_process_byte(byte);
 *         HAL_UART_Receive_IT(&huart2, &rx_buffer[0], 1);
 *     }
 * }
 */
