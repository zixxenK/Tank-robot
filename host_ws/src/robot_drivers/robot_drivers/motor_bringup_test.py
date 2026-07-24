#!/usr/bin/env python3
"""One-shot low-speed motor direction bring-up test for /cmd_vel."""

import time
from dataclasses import dataclass
from typing import List

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node


@dataclass
class _Phase:
    name: str
    linear: float
    angular: float
    duration: float


class MotorBringupTest(Node):
    def __init__(self) -> None:
        super().__init__("motor_bringup_test")

        self.declare_parameter("step_speed", 0.22)
        self.declare_parameter("step_duration", 1.2)
        self.declare_parameter("pause_duration", 0.6)
        self.declare_parameter("publish_rate_hz", 20.0)
        self.declare_parameter("track_width_m", 0.194)
        self.declare_parameter("start_delay", 1.0)

        speed = float(self.get_parameter("step_speed").value)
        step_duration = float(self.get_parameter("step_duration").value)
        pause_duration = float(self.get_parameter("pause_duration").value)
        publish_rate_hz = float(self.get_parameter("publish_rate_hz").value)
        track_width = float(self.get_parameter("track_width_m").value)
        self._start_delay = float(self.get_parameter("start_delay").value)

        turn_ang = (2.0 * speed) / max(track_width, 1e-3)

        # Sequence mirrors firmware self-test intent using cmd_vel only.
        self._phases: List[_Phase] = [
            _Phase("idle", 0.0, 0.0, pause_duration),
            _Phase("left_forward", speed, -turn_ang, step_duration),
            _Phase("idle", 0.0, 0.0, pause_duration),
            _Phase("left_reverse", -speed, turn_ang, step_duration),
            _Phase("idle", 0.0, 0.0, pause_duration),
            _Phase("right_forward", speed, turn_ang, step_duration),
            _Phase("idle", 0.0, 0.0, pause_duration),
            _Phase("right_reverse", -speed, -turn_ang, step_duration),
            _Phase("idle", 0.0, 0.0, pause_duration),
        ]

        self._phase_index = 0
        self._phase_start = time.time() + self._start_delay

        self._pub = self.create_publisher(Twist, "/cmd_vel", 10)
        period = 1.0 / max(publish_rate_hz, 1.0)
        self._timer = self.create_timer(period, self._tick)

        self.get_logger().warn(
            "Motor bring-up test armed. Keep robot lifted. "
            f"Starting in {self._start_delay:.1f}s."
        )

    def _publish(self, linear: float, angular: float) -> None:
        msg = Twist()
        msg.linear.x = float(linear)
        msg.angular.z = float(angular)
        self._pub.publish(msg)

    def publish_stop(self) -> None:
        self._publish(0.0, 0.0)

    def _tick(self) -> None:
        now = time.time()
        if self._phase_index >= len(self._phases):
            self._publish(0.0, 0.0)
            self.get_logger().info("Motor bring-up sequence complete.")
            self.destroy_node()
            rclpy.shutdown()
            return

        phase = self._phases[self._phase_index]
        elapsed = now - self._phase_start

        if elapsed < 0.0:
            self._publish(0.0, 0.0)
            return

        self._publish(phase.linear, phase.angular)

        if elapsed >= phase.duration:
            self.get_logger().info(f"Phase done: {phase.name}")
            self._phase_index += 1
            self._phase_start = now


def main(args=None) -> None:
    rclpy.init(args=args)
    node = MotorBringupTest()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        if rclpy.ok():
            node.publish_stop()
    finally:
        if rclpy.ok():
            node.destroy_node()
            rclpy.shutdown()


if __name__ == "__main__":
    main()
