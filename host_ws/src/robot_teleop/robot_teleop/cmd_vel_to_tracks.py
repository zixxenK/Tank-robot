#!/usr/bin/env python3
"""Convert /cmd_vel into explicit left/right track commands.

This node keeps tank-drive math centralized on the Rock64 and publishes
normalized per-track commands in the range [-1.0, 1.0] for expansion hubs
or consumers that prefer explicit track setpoints.
"""

import math
from pathlib import Path

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from std_msgs.msg import Float32
from robot_control.control_map import (
    default_control_map,
    load_control_map,
    twist_to_track_pair,
)


class CmdVelToTracks(Node):
    """Map linear/angular velocity to left and right track commands."""

    def __init__(self) -> None:
        super().__init__("cmd_vel_to_tracks")

        self.declare_parameter("control_map_path", "")
        self.declare_parameter("track_width_m", -1.0)
        self.declare_parameter("max_track_speed_mps", -1.0)
        self.declare_parameter("input_topic", "/cmd_vel")
        self.declare_parameter("left_topic", "/tracks/left_cmd")
        self.declare_parameter("right_topic", "/tracks/right_cmd")

        control_map = self._load_control_map(
            str(self.get_parameter("control_map_path").value or "")
        )
        self._track_width = self._positive_float_parameter(
            "track_width_m", control_map.track_width_m
        )
        self._max_speed = self._positive_float_parameter(
            "max_track_speed_mps", control_map.max_track_speed_mps
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

    def _load_control_map(self, configured_path: str):
        candidates = []
        if configured_path:
            candidates.append(Path(configured_path))
        candidates.append(
            Path(__file__).resolve().parents[2]
            / "robot_control"
            / "config"
            / "control_map.yaml"
        )
        try:
            from ament_index_python.packages import get_package_share_directory

            candidates.append(
                Path(get_package_share_directory("robot_control"))
                / "config"
                / "control_map.yaml"
            )
        except (ImportError, LookupError, RuntimeError):
            # Direct source-tree tests and non-ROS tooling do not have ament's
            # package index; the sibling-package candidate above is enough.
            pass
        for candidate in candidates:
            if not candidate.is_file():
                continue
            try:
                return load_control_map(candidate)
            except (OSError, ValueError, ImportError):
                pass
        return default_control_map()

    def _positive_float_parameter(self, name: str, default: float) -> float:
        try:
            value = float(self.get_parameter(name).value)
        except (TypeError, ValueError):
            return default
        return value if math.isfinite(value) and value > 0.0 else default

    def _on_cmd_vel(self, msg: Twist) -> None:
        # Keep the exact same standard-Twist conversion used by the hardened
        # serial bridge. This prevents a second, subtly different tank model.
        left_norm, right_norm = twist_to_track_pair(
            float(msg.linear.x),
            float(msg.angular.z),
            self._track_width,
            self._max_speed,
        )

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
