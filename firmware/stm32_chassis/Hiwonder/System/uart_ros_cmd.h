/**
 * @file uart_ros_cmd.h
 * @brief Simple ROS command handler for Hiwonder firmware
 */

#ifndef UART_ROS_CMD_H
#define UART_ROS_CMD_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>

// Function prototypes
void uart_ros_cmd_init(void);
void uart_ros_process_byte(uint8_t byte);
void uart_ros_execute_command(const char* cmd);

#ifdef __cplusplus
}
#endif

#endif /* UART_ROS_CMD_H */
