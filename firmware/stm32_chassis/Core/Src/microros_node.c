#include "microros_node.h"
#include "microros_transport.h"
#include "global.h"
#include "chassis.h"
#include <rmw_microxrcedds_c/config.h>
#include <uxr/client/profile/transport/custom/custom_transport.h>

static rcl_allocator_t allocator;
static rclc_support_t support;
static rcl_node_t node;
static rclc_executor_t executor;
static rcl_subscription_t subscription;
static geometry_msgs__msg__Twist twist_msg;

// External chassis control from chassis_porting.c
extern ChassisTypeDef *chassis;

// Velocity command callback
void velocity_command_callback(const void * msgin) {
    const geometry_msgs__msg__Twist * twist = (const geometry_msgs__msg__Twist *)msgin;
    
    // Convert ROS Twist message to chassis velocity
    // twist->linear.x: forward/backward velocity (m/s)
    // twist->angular.z: rotation rate (rad/s)
    
    if (chassis != NULL) {
        // Convert m/s to mm/s for the chassis system
        float vx_mm_s = twist->linear.x * 1000.0f;
        float angular_rate = twist->angular.z;
        
        // Call the chassis set_velocity function
        chassis->set_velocity(chassis, vx_mm_s, 0.0f, angular_rate);
    }
}

void microros_node_init(void) {
    // Initialize micro-ROS allocator
    allocator = rcl_get_default_allocator();
    
    // Create init_options
    rclc_support_init(&support, 0, NULL, &allocator);
    
    // Create node
    rclc_node_init_default(&node, "stm32_chassis_node", "", &support);
    
    // Create subscriber for velocity commands
    rclc_subscription_init_default(
        &subscription,
        &node,
        ROSIDL_GET_MSG_TYPE_SUPPORT(geometry_msgs, msg, Twist),
        "cmd_vel"
    );
    
    // Create executor
    rclc_executor_init(&executor, &support.context, 1, &allocator);
    rclc_executor_add_subscription(&executor, &subscription, &twist_msg, &velocity_command_callback, ON_NEW_DATA);
}

void microros_spin_once(void) {
    rclc_executor_spin_some(&executor, 100);
}