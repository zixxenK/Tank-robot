#!/usr/bin/env python3
"""stm32_serial_bridge.py — /cmd_vel → STM32 serial motor command bridge.

Subscribes to /cmd_vel (geometry_msgs/Twist), converts linear and angular
velocity into left/right motor commands, and writes them over UART to the
STM32 motor controller in the format:  <motor_id,dir,speed>\n
"""

import serial

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node


class STM32SerialBridge(Node):
    """Bridges /cmd_vel to an STM32 motor controller over UART."""

    def __init__(self):
        super().__init__("stm32_serial_bridge")

        self.declare_parameter("serial_port", "/dev/rock64_stm32")
        self.declare_parameter("baud_rate", 115200)
        self.declare_parameter("max_speed", 255)

        port = self.get_parameter("serial_port").value
        baud = self.get_parameter("baud_rate").value
        self._max = self.get_parameter("max_speed").value

        try:
            self._ser = serial.Serial(port, baud, timeout=1.0)
            self.get_logger().info(
                f"Serial bridge open on {port} @ {baud} baud"
            )
        except serial.SerialException as exc:
            self.get_logger().error(f"Cannot open {port}: {exc}")
            self._ser = None

        self._sub = self.create_subscription(
            Twist, "/cmd_vel", self._cmd_vel_cb, 10
        )

    def _cmd_vel_cb(self, msg: Twist):
        if self._ser is None or not self._ser.is_open:
            return

        lin = msg.linear.x
        ang = msg.angular.z

        left_vel = lin - ang
        right_vel = lin + ang

        left_speed = int(abs(left_vel) / 1.0 * self._max)
        right_speed = int(abs(right_vel) / 1.0 * self._max)

        left_dir = 1 if left_vel >= 0 else 0
        right_dir = 1 if right_vel >= 0 else 0

        left_speed = min(left_speed, self._max)
        right_speed = min(right_speed, self._max)

        cmd = (f"<0,{left_dir},{left_speed}>"
               f"<1,{right_dir},{right_speed}>\n")
        try:
            self._ser.write(cmd.encode())
        except serial.SerialException as exc:
            self.get_logger().warn(f"Serial write failed: {exc}")

    def destroy_node(self):
        if self._ser and self._ser.is_open:
            try:
                self._ser.write(b"<0,0,0><1,0,0>\n")
            except serial.SerialException:
                pass
            self._ser.close()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = STM32SerialBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
