#!/usr/bin/env python3
"""stm32_serial_bridge.py — /cmd_vel → STM32 serial motor command bridge.

Subscribes to /cmd_vel (geometry_msgs/Twist), converts linear and angular
velocity into left/right motor commands, and writes them over UART to the
STM32 motor controller in the format:  <motor_id,dir,speed>\n

Includes bidirectional communication with heartbeat monitoring and command
acknowledgment for safety.
"""

import serial
import threading
import time
import math

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node


class STM32SerialBridge(Node):
    """Bridge /cmd_vel to STM32 UART with heartbeat and smoothing."""

    def __init__(self):
        super().__init__("stm32_serial_bridge")

        self.declare_parameter("serial_port", "/dev/rock64_stm32")
        self.declare_parameter("baud_rate", 115200)
        self.declare_parameter("max_speed", 255)
        self.declare_parameter("heartbeat_timeout", 0.5)
        self.declare_parameter("heartbeat_interval", 0.1)
        self.declare_parameter("command_rate_hz", 50.0)
        self.declare_parameter("cmd_timeout", 0.25)
        self.declare_parameter("linear_slew_rate", 3.0)
        self.declare_parameter("angular_slew_rate", 6.0)

        port = self.get_parameter("serial_port").value
        baud = self.get_parameter("baud_rate").value
        self._max = self.get_parameter("max_speed").value
        self._heartbeat_timeout = self.get_parameter("heartbeat_timeout").value
        self._heartbeat_interval = self.get_parameter(
            "heartbeat_interval"
        ).value
        self._command_rate_hz = self.get_parameter("command_rate_hz").value
        self._cmd_timeout = self.get_parameter("cmd_timeout").value
        self._linear_slew_rate = self.get_parameter("linear_slew_rate").value
        self._angular_slew_rate = self.get_parameter("angular_slew_rate").value

        self._target_lin = 0.0
        self._target_ang = 0.0
        self._cmd_lin = 0.0
        self._cmd_ang = 0.0
        self._last_cmd_vel_time = time.time()
        self._last_send_time = time.time()
        self._last_sent_left = None
        self._last_sent_right = None

        try:
            self._ser = serial.Serial(port, baud, timeout=0.1)
            self.get_logger().info(
                f"Serial bridge open on {port} @ {baud} baud"
            )
        except serial.SerialException as exc:
            self.get_logger().error(f"Cannot open {port}: {exc}")
            self._ser = None

        # Safety state
        self._stm32_alive = True
        self._last_heartbeat_time = time.time()
        self._command_acknowledged = True
        self._lock = threading.Lock()

        # Start serial read thread for heartbeat/ack monitoring
        if self._ser:
            self._read_thread = threading.Thread(
                target=self._serial_read_loop, daemon=True
            )
            self._read_thread.start()

            # Start heartbeat send timer
            self._heartbeat_timer = self.create_timer(
                self._heartbeat_interval, self._send_heartbeat
            )

        self._sub = self.create_subscription(
            Twist, "/cmd_vel", self._cmd_vel_cb, 10
        )

        period = 1.0 / max(self._command_rate_hz, 1.0)
        self._command_timer = self.create_timer(period, self._drive_loop)

    def _serial_read_loop(self):
        """Background thread to read heartbeat and ack messages from STM32."""
        while rclpy.ok() and self._ser and self._ser.is_open:
            try:
                if self._ser.in_waiting > 0:
                    line = self._ser.readline().decode(
                        "utf-8", errors="ignore"
                    ).strip()
                    if line:
                        self._process_stm32_message(line)
                else:
                    time.sleep(0.01)
            except serial.SerialException as exc:
                self.get_logger().error(f"Serial read error: {exc}")
                break
            except (OSError, UnicodeError, ValueError) as exc:
                self.get_logger().error(
                    f"Unexpected error in read loop: {exc}"
                )
                break

    def _process_stm32_message(self, message):
        """Process incoming messages from STM32."""
        with self._lock:
            if message == "HB":  # Heartbeat from STM32
                self._last_heartbeat_time = time.time()
                if not self._stm32_alive:
                    self.get_logger().info("STM32 heartbeat resumed")
                    self._stm32_alive = True
            elif message == "ACK":  # Command acknowledgment
                self._command_acknowledged = True
            elif message.startswith("ERR:"):
                self.get_logger().warn(f"STM32 error: {message}")
            else:
                self.get_logger().debug(f"Unknown STM32 message: {message}")

    def _send_heartbeat(self):
        """Send periodic heartbeat to STM32 and check for timeout."""
        if self._ser is None or not self._ser.is_open:
            return

        # Check heartbeat timeout
        current_time = time.time()
        with self._lock:
            if (
                current_time - self._last_heartbeat_time
            ) > self._heartbeat_timeout:
                if self._stm32_alive:
                    self.get_logger().error(
                        "STM32 heartbeat timeout - commands disabled"
                    )
                    self._stm32_alive = False

        # Send heartbeat ping to STM32
        try:
            self._ser.write(b"PING\n")
        except serial.SerialException as exc:
            self.get_logger().warn(f"Heartbeat send failed: {exc}")

    def _cmd_vel_cb(self, msg: Twist):
        with self._lock:
            self._target_lin = msg.linear.x
            self._target_ang = msg.angular.z
            self._last_cmd_vel_time = time.time()

    def _slew(
        self,
        current: float,
        target: float,
        rate: float,
        dt: float,
    ) -> float:
        max_step = max(rate, 0.0) * max(dt, 0.0)
        delta = target - current
        if abs(delta) <= max_step:
            return target
        return current + math.copysign(max_step, delta)

    def _drive_loop(self):
        if self._ser is None or not self._ser.is_open:
            return

        now = time.time()
        dt = now - self._last_send_time
        self._last_send_time = now

        with self._lock:
            alive = self._stm32_alive
            stale = (now - self._last_cmd_vel_time) > self._cmd_timeout
            target_lin = 0.0 if stale else self._target_lin
            target_ang = 0.0 if stale else self._target_ang

        if not alive:
            return

        self._cmd_lin = self._slew(
            self._cmd_lin, target_lin, self._linear_slew_rate, dt
        )
        self._cmd_ang = self._slew(
            self._cmd_ang, target_ang, self._angular_slew_rate, dt
        )

        left_vel = self._cmd_lin - self._cmd_ang
        right_vel = self._cmd_lin + self._cmd_ang
        max_mag = max(1.0, abs(left_vel), abs(right_vel))
        left_vel /= max_mag
        right_vel /= max_mag

        left_speed = min(int(abs(left_vel) * self._max), self._max)
        right_speed = min(int(abs(right_vel) * self._max), self._max)
        left_dir = 1 if left_vel >= 0 else 0
        right_dir = 1 if right_vel >= 0 else 0

        if (
            left_speed == self._last_sent_left
            and right_speed == self._last_sent_right
            and now - self._last_cmd_vel_time <= self._cmd_timeout
        ):
            return

        cmd = (f"<0,{left_dir},{left_speed}>"
               f"<1,{right_dir},{right_speed}>\n")
        try:
            self._ser.write(cmd.encode())
            self._command_acknowledged = False
            self._last_sent_left = left_speed
            self._last_sent_right = right_speed
        except serial.SerialException as exc:
            self.get_logger().warn(f"Serial write failed: {exc}")

    def destroy_node(self):
        if self._ser and self._ser.is_open:
            try:
                # Send emergency stop before closing
                self._ser.write(b"<0,0,0><1,0,0>\n")
                time.sleep(0.1)  # Give STM32 time to process
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
