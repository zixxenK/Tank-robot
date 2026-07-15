#!/usr/bin/env python3
"""ps5_ros_bridge.py — PS5 DualSense controller → /cmd_vel bridge.

Reads joystick events from a DualSense controller (via /dev/input/jsX
or the SDL2 evdev interface) and publishes geometry_msgs/Twist messages
on /cmd_vel for the STM32 serial bridge to consume.
"""

import time

try:
    import rclpy
    from rclpy.node import Node
    from geometry_msgs.msg import Twist
except ImportError:
    class _FallbackVector3:
        def __init__(self):
            self.x = 0.0
            self.y = 0.0
            self.z = 0.0

    class _TwistFallback:
        def __init__(self):
            self.linear = _FallbackVector3()
            self.angular = _FallbackVector3()

    class _NodeFallback:
        def __init__(self, name):
            self._name = name

        def get_logger(self):
            class _Logger:
                def info(self, msg):
                    pass

                def warn(self, msg):
                    pass

                def error(self, msg):
                    pass

            return _Logger()

        def declare_parameter(self, _name, value=None):
            class _Parameter:
                def __init__(self, parameter_value):
                    self.value = parameter_value

            return _Parameter(value)

        def get_parameter(self, _name):
            class _Parameter:
                def __init__(self):
                    self.value = None

            return _Parameter()

        def create_publisher(self, _msg_type, _topic, _qos_profile):
            class _Publisher:
                def publish(self, msg):
                    pass

            return _Publisher()

        def create_timer(self, _timer_period_sec, _callback):
            return object()

        def destroy_node(self):
            pass

    class _FallbackRclpy:
        def init(self, args=None):
            pass

        def shutdown(self):
            pass

        def spin(self, node):
            pass

    Twist = _TwistFallback
    Node = _NodeFallback
    rclpy = _FallbackRclpy()


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
        self.declare_parameter("deadzone",          0.08)
        self.declare_parameter("expo",              0.35)
        self.declare_parameter("reconnect_interval_s", 1.0)

        self._max_lin = self.get_parameter("max_linear_speed").value
        self._max_ang = self.get_parameter("max_angular_speed").value
        self._joy_dev = self.get_parameter("joy_device").value
        rate_hz = self.get_parameter("publish_rate_hz").value
        self._deadzone = self.get_parameter("deadzone").value
        self._expo = self.get_parameter("expo").value
        self._reconnect_interval = float(
            self.get_parameter("reconnect_interval_s").value
        )

        self._pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self._axes = [0.0] * 8
        self._last_reconnect_attempt = 0.0
        self._last_missing_log = 0.0

        self._joy_fd = self._open_joystick(self._joy_dev)

        period = 1.0 / rate_hz
        self._timer = self.create_timer(period, self._publish_twist)
        self.get_logger().info(
            f"PS5 bridge started — device: {self._joy_dev}"
        )

    def _open_joystick(self, device: str):
        try:
            return open(device, "rb", buffering=0)  # noqa: SIM115
        except OSError as exc:
            self.get_logger().warn(
                f"Cannot open joystick {device}: {exc}. "
                "Publishing zero twist until device appears."
            )
            return None

    def _read_joystick(self):
        """Non-blocking read of a single Linux joystick event (8 bytes)."""
        if self._joy_fd is None:
            now = time.monotonic()
            if (
                (now - self._last_reconnect_attempt)
                >= self._reconnect_interval
            ):
                self._last_reconnect_attempt = now
                self._joy_fd = self._open_joystick(self._joy_dev)
            return

        import struct
        import select
        try:
            r, _, _ = select.select([self._joy_fd], [], [], 0)
            if not r:
                return
            data = self._joy_fd.read(8)
            if data and len(data) == 8:
                _, value, ev_type, number = struct.unpack("IhBB", data)
                if ev_type & 0x02:  # JS_EVENT_AXIS
                    if number < len(self._axes):
                        self._axes[number] = value / 32767.0
        except OSError:
            try:
                self._joy_fd.close()
            except OSError:
                pass
            self._joy_fd = None
            self._axes = [0.0] * len(self._axes)

    def _publish_twist(self):
        self._read_joystick()

        if self._joy_fd is None:
            now = time.monotonic()
            if (now - self._last_missing_log) >= 5.0:
                self._last_missing_log = now
                self.get_logger().warn(
                    "PS5 controller not connected; publishing zero /cmd_vel"
                )
            msg = Twist()
            self._pub.publish(msg)
            return

        def shape_axis(v: float) -> float:
            # Deadzone plus cubic blend gives finer low-speed stick control.
            if abs(v) < self._deadzone:
                return 0.0
            scaled = (abs(v) - self._deadzone) / max(
                1.0 - self._deadzone, 1e-6
            )
            shaped = (1.0 - self._expo) * scaled + self._expo * (scaled ** 3)
            return shaped if v >= 0.0 else -shaped

        lin_axis = shape_axis(-self._axes[self.LINEAR_AXIS])
        ang_axis = shape_axis(-self._axes[self.ANGULAR_AXIS])

        msg = Twist()
        msg.linear.x = lin_axis * self._max_lin
        msg.angular.z = ang_axis * self._max_ang
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
