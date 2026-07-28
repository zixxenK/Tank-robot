/**
 * @file uart_ros_bridge.h
 * @brief ROS protocol compatibility layer for Hiwonder STM32 firmware
 */

#ifndef UART_ROS_BRIDGE_H
#define UART_ROS_BRIDGE_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include "stm32f4xx_hal.h"

// Function prototypes
void uart_ros_bridge_init(void);
void uart_ros_bridge_process_byte(uint8_t byte);
void uart_ros_bridge_parse_command(const char* cmd);
void uart_ros_bridge_execute_motor_command(int motor_id, int direction, int speed);
void uart_ros_bridge_apply_to_chassis(void);
uint8_t uart_ros_bridge_check_timeout(void);
void uart_ros_bridge_send_heartbeat(void);
void uart_ros_bridge_send_ack(const char* msg);
void uart_ros_bridge_send_encoder_telemetry(int32_t left_encoder, int32_t right_encoder);
void uart_ros_bridge_periodic_task(void);

#ifdef __cplusplus
}
#endif

#endif /* UART_ROS_BRIDGE_H */
