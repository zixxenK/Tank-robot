#!/usr/bin/env python3
"""Minimal /cmd_vel -> STM32 velocity packet bridge.

This node is intentionally simple for bringup and protocol validation.
It converts:
- linear.x (m/s) -> vx_mm_s (mm/s)
- angular.z (rad/s) -> omega_rad_s (rad/s)

Packet format currently defaults to: struct.pack('<ff', vx_mm_s, omega_rad_s) + b'\n'
Adjust the format in one place once firmware framing is finalized.
"""

import struct
from typing import Optional

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node

try:
    import serial
except ImportError:  # pragma: no cover
    serial = None


class ChassisBridge(Node):
    """Translate /cmd_vel into STM32 velocity packets over UART."""

    def __init__(self) -> None:
        super().__init__("chassis_bridge")

        self.declare_parameter("serial_port", "/dev/rock64_stm32")
        self.declare_parameter("baud_rate", 115200)
        self.declare_parameter("write_serial", False)
        self.declare_parameter("topic", "/cmd_vel")

        self._port: str = str(self.get_parameter("serial_port").value)
        self._baud: int = int(self.get_parameter("baud_rate").value)
        self._write_serial: bool = bool(self.get_parameter("write_serial").value)
        topic: str = str(self.get_parameter("topic").value)

        self._ser: Optional["serial.Serial"] = None

        if self._write_serial:
            self._open_serial()
        else:
            self.get_logger().info(
                "write_serial=false; running in dry-run mode (logging packets only)."
            )

        self._sub = self.create_subscription(Twist, topic, self._cmd_vel_callback, 10)
        self.get_logger().info(f"Chassis Bridge initialized. Listening on {topic}")

    def _open_serial(self) -> None:
        if serial is None:
            self.get_logger().error("pyserial is not installed; cannot open serial port.")
            return

        try:
            self._ser = serial.Serial(self._port, self._baud, timeout=0.05)
            self.get_logger().info(f"Serial open: {self._port} @ {self._baud}")
        except serial.SerialException as exc:
            self.get_logger().error(f"Failed to open serial port {self._port}: {exc}")
            self._ser = None

    def _encode_packet(self, vx_mm_s: float, omega_rad_s: float) -> bytes:
        # Firmware placeholder framing: little-endian float32 pair + newline.
        return struct.pack("<ff", vx_mm_s, omega_rad_s) + b"\n"

    def _cmd_vel_callback(self, msg: Twist) -> None:
        vx_mm_s = float(msg.linear.x) * 1000.0
        omega_rad_s = float(msg.angular.z)

        packet = self._encode_packet(vx_mm_s, omega_rad_s)

        self.get_logger().debug(
            f"cmd_vel -> vx={vx_mm_s:.2f} mm/s omega={omega_rad_s:.3f} rad/s"
        )

        if not self._write_serial:
            return

        if self._ser is None or not self._ser.is_open:
            self.get_logger().warn("Serial not available; dropping packet.")
            return

        try:
            self._ser.write(packet)
        except serial.SerialException as exc:
            self.get_logger().warn(f"Serial write failed: {exc}")

    def destroy_node(self) -> bool:
        if self._ser is not None and self._ser.is_open:
            try:
                self._ser.close()
            except Exception:
                pass
        return super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = ChassisBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
