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
"""ROS2 node for terrain classification using IMU data."""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu
from std_msgs.msg import String
from terrain_adaptation.terrain_classifier import TerrainClassifier


class TerrainClassifierNode(Node):
    """ROS2 node for terrain classification."""

    def __init__(self) -> None:
        super().__init__("terrain_classifier")

        # Parameters
        self.declare_parameter("imu_topic", "/stm32/imu")
        self.declare_parameter("terrain_topic", "/terrain/type")
        self.declare_parameter("window_size", 100)
        self.declare_parameter("sample_rate", 50.0)

        self._imu_topic = self.get_parameter("imu_topic").value
        self._terrain_topic = self.get_parameter("terrain_topic").value
        self._window_size = self.get_parameter("window_size").value
        self._sample_rate = self.get_parameter("sample_rate").value

        # Initialize classifier
        self._classifier = TerrainClassifier(
            window_size=self._window_size,
            sample_rate=self._sample_rate
        )

        # Subscribers and publishers
        self._imu_sub = self.create_subscription(
            Imu, self._imu_topic, self._imu_callback, 10
        )
        self._terrain_pub = self.create_publisher(
            String, self._terrain_topic, 10
        )

        self.get_logger().info("Terrain classifier node initialized")

    def _imu_callback(self, msg: Imu) -> None:
        """Process IMU message and classify terrain."""
        # Add IMU data to classifier
        self._classifier.add_imu_data(
            accel_x=msg.linear_acceleration.x,
            accel_y=msg.linear_acceleration.y,
            accel_z=msg.linear_acceleration.z,
            gyro_x=msg.angular_velocity.x,
            gyro_y=msg.angular_velocity.y,
            gyro_z=msg.angular_velocity.z,
        )

        # Classify terrain if ready
        if self._classifier.is_ready():
            terrain = self._classifier.classify()
            confidence = self._classifier.get_confidence()

            # Publish terrain type
            terrain_msg = String()
            terrain_msg.data = f"{terrain.value}:{confidence:.2f}"
            self._terrain_pub.publish(terrain_msg)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = TerrainClassifierNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
