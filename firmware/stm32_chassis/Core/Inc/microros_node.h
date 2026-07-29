#ifndef MICROROS_NODE_H
#define MICROROS_NODE_H

#include <rcl/rcl.h>
#include <rcl/error.h>
#include <rclc/rclc.h>
#include <rclc/executor.h>
#include <geometry_msgs/msg/twist.h>

void microros_node_init(void);
void microros_spin_once(void);

#endif // MICROROS_NODE_H