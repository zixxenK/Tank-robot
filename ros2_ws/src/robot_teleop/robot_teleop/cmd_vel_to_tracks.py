#!/usr/bin/env python3
"""Convert /cmd_vel into explicit left/right track commands.

This node keeps tank-drive math centralized on the Rock64 and publishes
normalized per-track commands in the range [-1.0, 1.0] for expansion hubs
or micro-ROS clients that prefer direct track setpoints.
"""

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from std_msgs.msg import Float32


class CmdVelToTracks(Node):
    """Map linear/angular velocity to left and right track commands."""

    def __init__(self) -> None:
        super().__init__("cmd_vel_to_tracks")

        self.declare_parameter("track_width_m", 0.194)
        self.declare_parameter("max_track_speed_mps", 0.8)
        self.declare_parameter("input_topic", "/cmd_vel")
        self.declare_parameter("left_topic", "/tracks/left_cmd")
        self.declare_parameter("right_topic", "/tracks/right_cmd")

        self._track_width = float(self.get_parameter("track_width_m").value)
        self._max_speed = float(
            self.get_parameter("max_track_speed_mps").value
        )
        input_topic = str(self.get_parameter("input_topic").value)
        left_topic = str(self.get_parameter("left_topic").value)
        right_topic = str(self.get_parameter("right_topic").value)

        self._left_pub = self.create_publisher(Float32, left_topic, 20)
        self._right_pub = self.create_publisher(Float32, right_topic, 20)

        self.create_subscription(Twist, input_topic, self._on_cmd_vel, 20)
        self.get_logger().info(
            "cmd_vel_to_tracks active: "
            f"{input_topic} -> ({left_topic}, {right_topic})"
        )

    def _on_cmd_vel(self, msg: Twist) -> None:
        # Differential-drive model:
        # v_l = v - omega*(L/2), v_r = v + omega*(L/2)
        v = float(msg.linear.x)
        omega = float(msg.angular.z)
        half_w = self._track_width * 0.5

        v_left = v - omega * half_w
        v_right = v + omega * half_w

        # Normalize to [-1, 1] for downstream PWM/current mapping.
        scale = max(self._max_speed, 1e-6)
        left_norm = max(min(v_left / scale, 1.0), -1.0)
        right_norm = max(min(v_right / scale, 1.0), -1.0)

        left_msg = Float32()
        right_msg = Float32()
        left_msg.data = float(left_norm)
        right_msg.data = float(right_norm)

        self._left_pub.publish(left_msg)
        self._right_pub.publish(right_msg)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = CmdVelToTracks()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
