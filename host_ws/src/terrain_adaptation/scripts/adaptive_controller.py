#!/usr/bin/env python3
# Copyright 2026 Tank Robot Team
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
"""ROS2 node for adaptive control based on terrain classification."""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu
from geometry_msgs.msg import Twist
from std_msgs.msg import String
from terrain_adaptation.terrain_classifier import TerrainClassifier
from terrain_adaptation.adaptive_controller import AdaptiveController


class AdaptiveControllerNode(Node):
    """ROS2 node for adaptive control."""

    def __init__(self) -> None:
        super().__init__("adaptive_controller")

        # Parameters
        self.declare_parameter("imu_topic", "/stm32/imu")
        # Terrain adaptation transforms an autonomous proposal.  It must not
        # publish into the PS5 /cmd_vel operator lane or directly to hardware.
        self.declare_parameter("cmd_vel_input", "/agent/cmd_vel_planned")
        self.declare_parameter("cmd_vel_output", "/agent/cmd_vel_proposed")
        self.declare_parameter("terrain_topic", "/terrain/type")
        self.declare_parameter("window_size", 100)
        self.declare_parameter("sample_rate", 50.0)

        self._imu_topic = self.get_parameter("imu_topic").value
        self._cmd_vel_input = self.get_parameter("cmd_vel_input").value
        self._cmd_vel_output = self.get_parameter("cmd_vel_output").value
        self._terrain_topic = self.get_parameter("terrain_topic").value
        self._window_size = self.get_parameter("window_size").value
        self._sample_rate = self.get_parameter("sample_rate").value

        # Initialize classifier and controller
        self._terrain_classifier = TerrainClassifier(
            window_size=self._window_size,
            sample_rate=self._sample_rate
        )
        self._adaptive_controller = AdaptiveController(self._terrain_classifier)

        # Subscribers and publishers
        self._imu_sub = self.create_subscription(
            Imu, self._imu_topic, self._imu_callback, 10
        )
        self._cmd_vel_sub = self.create_subscription(
            Twist, self._cmd_vel_input, self._cmd_vel_callback, 10
        )
        self._cmd_vel_pub = self.create_publisher(
            Twist, self._cmd_vel_output, 10
        )
        self._terrain_pub = self.create_publisher(
            String, self._terrain_topic, 10
        )

        self.get_logger().info("Adaptive controller node initialized")

    def _imu_callback(self, msg: Imu) -> None:
        """Process IMU message and update terrain classification."""
        # Update adaptive controller with IMU data
        self._adaptive_controller.update(
            accel_x=msg.linear_acceleration.x,
            accel_y=msg.linear_acceleration.y,
            accel_z=msg.linear_acceleration.z,
            gyro_x=msg.angular_velocity.x,
            gyro_y=msg.angular_velocity.y,
            gyro_z=msg.angular_velocity.z,
        )

        # Publish terrain type
        terrain = self._adaptive_controller.get_current_terrain()
        confidence = self._terrain_classifier.get_confidence()

        terrain_msg = String()
        terrain_msg.data = f"{terrain.value}:{confidence:.2f}"
        self._terrain_pub.publish(terrain_msg)

    def _cmd_vel_callback(self, msg: Twist) -> None:
        """Process velocity command and adapt based on terrain."""
        # Adapt command based on current terrain
        adapted_linear, adapted_angular = self._adaptive_controller.adapt_command(
            linear_x=msg.linear.x,
            angular_z=msg.angular.z,
        )

        # Publish adapted command
        adapted_cmd = Twist()
        adapted_cmd.linear.x = adapted_linear
        adapted_cmd.linear.y = msg.linear.y
        adapted_cmd.linear.z = msg.linear.z
        adapted_cmd.angular.x = msg.angular.x
        adapted_cmd.angular.y = msg.angular.y
        adapted_cmd.angular.z = adapted_angular

        self._cmd_vel_pub.publish(adapted_cmd)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = AdaptiveControllerNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
