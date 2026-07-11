#!/usr/bin/env python3
"""ps5_ros_bridge.py — PS5 DualSense controller → /cmd_vel bridge.

Reads joystick events from a DualSense controller (via /dev/input/jsX
or the SDL2 evdev interface) and publishes geometry_msgs/Twist messages
on /cmd_vel for the robot_drivers serial bridge to consume.
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist


class PS5RosBridge(Node):
    """Translates PS5 controller axes to Twist and publishes /cmd_vel."""

    LINEAR_AXIS = 1   # Left stick vertical  (axis 1)
    ANGULAR_AXIS = 3  # Right stick horizontal (axis 3)

    def __init__(self):
        super().__init__("ps5_ros_bridge")

        self.declare_parameter("max_linear_speed",  0.5)
        self.declare_parameter("max_angular_speed", 1.0)
        self.declare_parameter("joy_device",        "/dev/input/js0")
        self.declare_parameter("publish_rate_hz",   20.0)

        self._max_lin = self.get_parameter("max_linear_speed").value
        self._max_ang = self.get_parameter("max_angular_speed").value
        self._joy_dev = self.get_parameter("joy_device").value
        rate_hz       = self.get_parameter("publish_rate_hz").value

        self._pub  = self.create_publisher(Twist, "/cmd_vel", 10)
        self._axes = [0.0] * 8

        self._joy_fd = self._open_joystick(self._joy_dev)

        period = 1.0 / rate_hz
        self._timer = self.create_timer(period, self._publish_twist)
        self.get_logger().info(
            f"PS5 bridge started — device: {self._joy_dev}"
        )

    def _open_joystick(self, device: str):
        try:
            return open(device, "rb")  # noqa: SIM115
        except OSError as exc:
            self.get_logger().warn(
                f"Cannot open joystick {device}: {exc}. "
                "Publishing zero twist until device appears."
            )
            return None

    def _read_joystick(self):
        """Non-blocking read of a single Linux joystick event (8 bytes)."""
        if self._joy_fd is None:
            self._joy_fd = self._open_joystick(self._joy_dev)
            return

        import struct
        import select
        r, _, _ = select.select([self._joy_fd], [], [], 0)
        if not r:
            return
        data = self._joy_fd.read(8)
        if data and len(data) == 8:
            _, value, ev_type, number = struct.unpack("IhBB", data)
            if ev_type & 0x02:  # JS_EVENT_AXIS
                if number < len(self._axes):
                    self._axes[number] = value / 32767.0

    def _publish_twist(self):
        self._read_joystick()

        msg = Twist()
        msg.linear.x  = -self._axes[self.LINEAR_AXIS]  * self._max_lin
        msg.angular.z = -self._axes[self.ANGULAR_AXIS] * self._max_ang
        self._pub.publish(msg)

    def destroy_node(self):
        if self._joy_fd:
            self._joy_fd.close()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = PS5RosBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
