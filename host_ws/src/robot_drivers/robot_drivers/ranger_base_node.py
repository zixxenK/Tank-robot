#!/usr/bin/env python3
"""
ranger_base_node.py - ROS2 base controller for ROCK64-RANGER Mk1

This node:
1. Subscribes to cmd_vel (geometry_msgs/Twist)
2. Uses differential drive inverse kinematics to convert linear/angular velocity to left/right wheel target RPS
3. Publishes motor commands to the STM32 via the binary protocol bridge

Differential Drive Kinematics:
- v_left = (linear_velocity - angular_velocity * track_width / 2) / wheel_radius
- v_right = (linear_velocity + angular_velocity * track_width / 2) / wheel_radius
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import Float32MultiArray  # type: ignore


class RangerBaseNode(Node):
    """ROS2 base controller for differential drive robot."""
    
    def __init__(self):
        super().__init__('ranger_base_node')
        
        # Robot parameters (adjust based on your actual robot)
        self.declare_parameter('wheel_radius', 0.054)  # 54mm wheel radius (meters)
        self.declare_parameter('track_width', 0.2038)  # 203.8mm track width (meters)
        self.declare_parameter('max_wheel_rps', 10.0)  # Max wheel RPS
        self.declare_parameter('cmd_vel_timeout', 0.5)  # Command timeout (seconds)
        
        self.wheel_radius = self.get_parameter('wheel_radius').value
        self.track_width = self.get_parameter('track_width').value
        self.max_wheel_rps = self.get_parameter('max_wheel_rps').value
        self.cmd_vel_timeout = self.get_parameter('cmd_vel_timeout').value
        
        # Motor command publisher (will be consumed by stm32_hardened_bridge)
        self.motor_cmd_pub = self.create_publisher(
            Float32MultiArray, 
            '/stm32/motor_commands', 
            10
        )
        
        # cmd_vel subscriber
        self.cmd_vel_sub = self.create_subscription(
            Twist,
            '/cmd_vel',
            self.cmd_vel_callback,
            10
        )
        
        # State
        self.last_cmd_time = 0.0
        self.target_left_rps = 0.0
        self.target_right_rps = 0.0
        
        # Watchdog timer
        self.watchdog_timer = self.create_timer(
            0.1,  # 10Hz
            self.watchdog_callback
        )
        
        self.get_logger().info('Ranger Base Node initialized')
        self.get_logger().info(f'Wheel radius: {self.wheel_radius}m')
        self.get_logger().info(f'Track width: {self.track_width}m')
        self.get_logger().info(f'Max wheel RPS: {self.max_wheel_rps}')
    
    def cmd_vel_callback(self, msg: Twist) -> None:
        """Handle cmd_vel messages and convert to wheel RPS."""
        linear_velocity: float = float(msg.linear.x)  # m/s
        angular_velocity: float = float(msg.angular.z)  # rad/s
        
        # Differential drive inverse kinematics
        # v = linear velocity, ω = angular velocity
        # v_left = (v - ω * L/2) / r
        # v_right = (v + ω * L/2) / r
        
        left_velocity: float = (linear_velocity - angular_velocity * self.track_width / 2.0)  # type: ignore
        right_velocity: float = (linear_velocity + angular_velocity * self.track_width / 2.0)  # type: ignore
        
        # Convert velocity (m/s) to RPS (revolutions per second)
        # RPS = velocity / (2 * π * wheel_radius)
        left_rps: float = left_velocity / (2.0 * 3.14159 * self.wheel_radius)  # type: ignore
        right_rps: float = right_velocity / (2.0 * 3.14159 * self.wheel_radius)  # type: ignore
        
        # Clamp to maximum RPS
        left_rps = max(-self.max_wheel_rps, min(self.max_wheel_rps, left_rps))  # type: ignore
        right_rps = max(-self.max_wheel_rps, min(self.max_wheel_rps, right_rps))  # type: ignore
        
        # Store targets
        self.target_left_rps = left_rps
        self.target_right_rps = right_rps
        
        # Update timestamp
        import time
        self.last_cmd_time = time.time()
        
        # Publish motor commands
        self.publish_motor_commands()
    
    def publish_motor_commands(self) -> None:
        """Publish motor commands to STM32 bridge."""
        # Normalize RPS to -1.0 to 1.0 range for STM32
        left_normalized: float = self.target_left_rps / self.max_wheel_rps  # type: ignore
        right_normalized: float = self.target_right_rps / self.max_wheel_rps  # type: ignore
        
        # Create motor command message
        # Format: [motor_id_0, rps_0, motor_id_1, rps_1]
        motor_cmd = Float32MultiArray()
        motor_cmd.data = [
            0.0,  # Motor 0 ID
            left_normalized,  # Motor 0 RPS (normalized)
            1.0,  # Motor 1 ID
            right_normalized  # Motor 1 RPS (normalized)
        ]
        
        self.motor_cmd_pub.publish(motor_cmd)
    
    def watchdog_callback(self) -> None:
        """Watchdog to send zero commands if cmd_vel times out."""
        import time
        current_time: float = time.time()
        
        if (current_time - self.last_cmd_time) > self.cmd_vel_timeout:  # type: ignore
            # Command timeout - send zero commands
            if self.target_left_rps != 0.0 or self.target_right_rps != 0.0:
                self.get_logger().warn('cmd_vel timeout, stopping motors')
                self.target_left_rps = 0.0
                self.target_right_rps = 0.0
                self.publish_motor_commands()


def main(args=None):
    rclpy.init(args=args)
    node = RangerBaseNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        # Send zero commands before shutdown
        node.target_left_rps = 0.0
        node.target_right_rps = 0.0
        node.publish_motor_commands()
        
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
