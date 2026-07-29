/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file    microros_node.c
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

#include "microros_node.h"
#include "microros_transport.h"
#include "usart.h"
#include <rcl/rcl.h>
#include <rcl/error_handling.h>
#include <rclc/rclc.h>
#include <rclc/executor.h>
#include <geometry_msgs/msg/twist.h>
#include <std_msgs/msg/int32.h>
#include <std_msgs/msg/float32.h>

// micro-ROS entities
static rcl_allocator_t allocator;
static rcl_support_t support;
static rcl_node_t node;
static rclc_executor_t executor;
static rcl_subscription_t cmd_vel_sub;
static rcl_publisher_t motor_telemetry_pub;

// Message objects
static geometry_msgs__msg__Twist cmd_vel_msg;
static std_msgs__msg__Int32 motor_left_msg;
static std_msgs__msg__Int32 motor_right_msg;

// Motor control state
static float target_linear_velocity = 0.0f;
static float target_angular_velocity = 0.0f;
static int16_t motor_left_speed = 0;
static int16_t motor_right_speed = 0;

// Control parameters
#define MAX_MOTOR_SPEED 255
#define WHEELBASE 0.3f  // meters
#define WHEEL_RADIUS 0.065f  // meters

// Error handling macro
#define RCCHECK(fn) { rcl_ret_t temp_rc = fn; if((temp_rc != RCL_RET_OK)){ error_loop(); } }
#define RCSOFTCHECK(fn) { rcl_ret_t temp_rc = fn; if((temp_rc != RCL_RET_OK)){ } }

/**
 * @brief Error loop - halts execution on critical errors
 */
void error_loop(void) {
    while(1) {
        // Flash LED or indicate error state
        osDelay(100);
    }
}

/**
 * @brief Callback for /cmd_vel subscription
 */
void cmd_vel_callback(const void *msg_in) {
    const geometry_msgs__msg__Twist *msg = (const geometry_msgs__msg__Twist *)msg_in;
    
    // Store target velocities
    target_linear_velocity = msg->linear.x;
    target_angular_velocity = msg->angular.z;
    
    // Convert to motor speeds (differential drive kinematics)
    float left_vel = (target_linear_velocity - (target_angular_velocity * WHEELBASE / 2.0f)) / WHEEL_RADIUS;
    float right_vel = (target_linear_velocity + (target_angular_velocity * WHEELBASE / 2.0f)) / WHEEL_RADIUS;
    
    // Scale to PWM range
    motor_left_speed = (int16_t)(left_vel / MAX_LINEAR_VELOCITY * MAX_MOTOR_SPEED);
    motor_right_speed = (int16_t)(right_vel / MAX_LINEAR_VELOCITY * MAX_MOTOR_SPEED);
    
    // Clamp to valid range
    motor_left_speed = (motor_left_speed > MAX_MOTOR_SPEED) ? MAX_MOTOR_SPEED : 
                      (motor_left_speed < -MAX_MOTOR_SPEED) ? -MAX_MOTOR_SPEED : motor_left_speed;
    motor_right_speed = (motor_right_speed > MAX_MOTOR_SPEED) ? MAX_MOTOR_SPEED : 
                       (motor_right_speed < -MAX_MOTOR_SPEED) ? -MAX_MOTOR_SPEED : motor_right_speed;
    
    // Apply motor commands (this would interface with your existing motor control)
    // For now, this is a placeholder for your motor control implementation
    apply_motor_commands(motor_left_speed, motor_right_speed);
}

/**
 * @brief Apply motor commands (placeholder for your motor control implementation)
 */
void apply_motor_commands(int16_t left_speed, int16_t right_speed) {
    // TODO: Integrate with your existing motor control code
    // This would typically set PWM values for motor drivers
    // Example:
    // set_motor_pwm(MOTOR_LEFT, abs(left_speed), left_speed >= 0);
    // set_motor_pwm(MOTOR_RIGHT, abs(right_speed), right_speed >= 0);
}

/**
 * @brief Publish motor telemetry
 */
void publish_motor_telemetry(void) {
    motor_left_msg.data = motor_left_speed;
    motor_right_msg.data = motor_right_speed;
    
    RCSOFTCHECK(rcl_publish(&motor_telemetry_pub, &motor_left_msg, NULL));
    RCSOFTCHECK(rcl_publish(&motor_telemetry_pub, &motor_right_msg, NULL));
}

/**
 * @brief Initialize micro-ROS node
 */
int microros_node_init(void) {
    // Initialize transport
    microros_transport_init();
    
    // Set transport functions
    rmw_uros_set_custom_transport(
        true,
        NULL,  // No context needed for our implementation
        microros_transport_open,
        microros_transport_close,
        microros_transport_write,
        microros_transport_read
    );
    
    // Initialize allocator
    allocator = rcl_get_default_allocator();
    
    // Initialize support
    RCCHECK(rclc_support_init(&support, 0, &allocator));
    
    // Create node
    RCCHECK(rclc_node_init_default(&node, "stm32_motor_controller", "", &support));
    
    // Create /cmd_vel subscriber
    RCCHECK(rclc_subscription_init_default(
        &cmd_vel_sub,
        &node,
        ROSIDL_GET_MSG_TYPE_SUPPORT(geometry_msgs, msg, Twist),
        "/cmd_vel"
    ));
    
    // Create motor telemetry publishers
    RCCHECK(rclc_publisher_init_default(
        &motor_telemetry_pub,
        &node,
        ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Int32),
        "/motor_left_speed"
    ));
    
    // Initialize messages
    geometry_msgs__msg__Twist__init(&cmd_vel_msg);
    std_msgs__msg__Int32__init(&motor_left_msg);
    std_msgs__msg__Int32__init(&motor_right_msg);
    
    // Initialize executor
    RCCHECK(rclc_executor_init(&executor, &support.context, 1, &allocator));
    RCCHECK(rclc_executor_add_subscription(&executor, &cmd_vel_sub, &cmd_vel_msg, &cmd_vel_callback, ON_NEW_DATA));
    
    return 0;
}

/**
 * @brief Spin the micro-ROS node (call periodically from FreeRTOS task)
 */
void microros_node_spin(void) {
    // Timeout for executor spin
    const unsigned int timeout = 100; // milliseconds
    
    // Spin executor
    RCSOFTCHECK(rclc_executor_spin_some(&executor, RCL_MS_TO_NS(timeout)));
    
    // Publish telemetry periodically
    static uint32_t last_telemetry_time = 0;
    if (HAL_GetTick() - last_telemetry_time > 100) { // 10Hz telemetry
        publish_motor_telemetry();
        last_telemetry_time = HAL_GetTick();
    }
}

/**
 * @brief Cleanup micro-ROS node
 */
void microros_node_cleanup(void) {
    // Cleanup publisher
    RCSOFTCHECK(rcl_publisher_fini(&motor_telemetry_pub, &node));
    
    // Cleanup subscription
    RCSOFTCHECK(rcl_subscription_fini(&cmd_vel_sub, &node));
    
    // Cleanup executor
    RCSOFTCHECK(rclc_executor_fini(&executor));
    
    // Cleanup node
    RCSOFTCHECK(rcl_node_fini(&node));
    
    // Cleanup support
    RCSOFTCHECK(rclc_support_fini(&support));
    
    // Cleanup messages
    geometry_msgs__msg__Twist__fini(&cmd_vel_msg);
    std_msgs__msg__Int32__fini(&motor_left_msg);
    std_msgs__msg__Int32__fini(&motor_right_msg);
}