#!/usr/bin/env python3
"""Fail-closed relay for autonomous proposal commands.

This node never relays autonomy to ``/cmd_vel`` by default.  Its output is
the agent proposal boundary, which still requires a fresh ``/agent/heartbeat``
at the safety gateway before it can reach the motors.
"""

from __future__ import annotations

import math

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node


class CmdVelRelay(Node):
    """Forward planner commands to the safety gateway after finite checks."""

    def __init__(self) -> None:
        super().__init__("cmd_vel_relay")
        self.declare_parameter("input_topic", "/agent/cmd_vel_planned")
        self.declare_parameter("output_topic", "/agent/cmd_vel_proposed")
        input_topic = str(self.get_parameter("input_topic").value)
        output_topic = str(self.get_parameter("output_topic").value)
        self._publisher = self.create_publisher(Twist, output_topic, 10)
        self._subscription = self.create_subscription(
            Twist, input_topic, self._on_command, 10
        )
        self.get_logger().info(
            f"Relaying finite autonomous proposals {input_topic} -> {output_topic}"
        )

    def _on_command(self, message: Twist) -> None:
        """Forward a command or publish a zero command when it is invalid."""
        values = (
            message.linear.x,
            message.linear.y,
            message.linear.z,
            message.angular.x,
            message.angular.y,
            message.angular.z,
        )
        if not all(math.isfinite(float(value)) for value in values):
            self.get_logger().error("Rejected non-finite autonomous command")
            self._publisher.publish(Twist())
            return

        forwarded = Twist()
        forwarded.linear.x = float(message.linear.x)
        forwarded.linear.y = float(message.linear.y)
        forwarded.linear.z = float(message.linear.z)
        forwarded.angular.x = float(message.angular.x)
        forwarded.angular.y = float(message.angular.y)
        forwarded.angular.z = float(message.angular.z)
        self._publisher.publish(forwarded)


def main(args=None) -> None:
    """Run the command relay."""
    rclpy.init(args=args)
    node = CmdVelRelay()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
