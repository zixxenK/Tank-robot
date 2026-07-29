#include "microros_node.h"
#include "global.h"
#include "chassis.h"

extern ChassisTypeDef *chassis;

void velocity_command_callback(const void * msgin) {
    // Stub implementation - will be replaced with micro-ROS callback
    // For now, just stop the motors
    if (chassis != NULL) {
        chassis->set_velocity(chassis, 0.0f, 0.0f, 0.0f);
    }
}

void microros_node_init(void) {
    // Stub implementation - micro-ROS initialization will go here
}

void microros_spin_once(void) {
    // Stub implementation - micro-ROS spinning will go here
}