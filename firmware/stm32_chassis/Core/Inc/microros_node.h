/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file    microros_node.h
  * @brief   micro-ROS node implementation for STM32F407 tank robot
  ******************************************************************************
  * @attention
  *
  * This file implements a micro-ROS node that:
  * - Subscribes to /cmd_vel (geometry_msgs/Twist) for velocity commands
  * - Publishes motor telemetry to /motor_telemetry
  * - Handles motor control via local PWM generation
  *
  ******************************************************************************
  */
/* USER CODE END Header */

#ifndef MICROROS_NODE_H
#define MICROROS_NODE_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <stdbool.h>

// Control parameters
#define MAX_LINEAR_VELOCITY 1.0f  // m/s
#define MAX_ANGULAR_VELOCITY 2.0f  // rad/s

/**
 * @brief Initialize micro-ROS node
 * @return 0 on success, -1 on error
 */
int microros_node_init(void);

/**
 * @brief Spin the micro-ROS node (call periodically from FreeRTOS task)
 */
void microros_node_spin(void);

/**
 * @brief Cleanup micro-ROS node
 */
void microros_node_cleanup(void);

/**
 * @brief Apply motor commands (placeholder for your motor control implementation)
 * @param left_speed Left motor speed (-255 to 255)
 * @param right_speed Right motor speed (-255 to 255)
 */
void apply_motor_commands(int16_t left_speed, int16_t right_speed);

/**
 * @brief Error loop - halts execution on critical errors
 */
void error_loop(void);

#ifdef __cplusplus
}
#endif

#endif /* MICROROS_NODE_H */