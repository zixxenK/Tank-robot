#!/usr/bin/env python3
"""One-shot CLI tester for STM32 self-test over ROS topics.

Publishes /stm32/self_test once and waits for /stm32/self_test_result.
Returns exit code 0 on pass, 1 on fail/timeout.
"""

import time
from typing import Optional

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool
from std_msgs.msg import Empty


class STM32SelftestCLI(Node):
    def __init__(self) -> None:
        super().__init__("stm32_selftest_cli")

        self.declare_parameter("timeout_s", 15.0)
        self._timeout_s = float(self.get_parameter("timeout_s").value)

        self._result: Optional[bool] = None
        self._pub = self.create_publisher(Empty, "/stm32/self_test", 10)
        self._sub = self.create_subscription(
            Bool,
            "/stm32/self_test_result",
            self._result_cb,
            10,
        )

    def _result_cb(self, msg: Bool) -> None:
        self._result = bool(msg.data)

    def run(self) -> int:
        end_time = time.monotonic() + max(self._timeout_s, 0.1)

        # Give publisher/subscriber graph a brief moment to connect.
        warmup_end = time.monotonic() + 0.3
        while rclpy.ok() and time.monotonic() < warmup_end:
            rclpy.spin_once(self, timeout_sec=0.05)

        self.get_logger().info("Triggering STM32 self-test")
        self._pub.publish(Empty())

        while rclpy.ok() and time.monotonic() < end_time:
            rclpy.spin_once(self, timeout_sec=0.1)
            if self._result is not None:
                if self._result:
                    self.get_logger().info("SELFTEST PASS")
                    return 0

                self.get_logger().error("SELFTEST FAIL")
                return 1

        self.get_logger().error("SELFTEST TIMEOUT")
        return 1


def main(args=None) -> None:
    rclpy.init(args=args)
    node = STM32SelftestCLI()

    exit_code = 1
    try:
        exit_code = node.run()
    except KeyboardInterrupt:
        node.get_logger().warn("Interrupted")
        exit_code = 1
    finally:
        node.destroy_node()
        rclpy.shutdown()

    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
