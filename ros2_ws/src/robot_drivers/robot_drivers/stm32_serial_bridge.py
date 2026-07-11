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

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node


class STM32SerialBridge(Node):
    """Bridges /cmd_vel to an STM32 motor controller over UART with safety features."""

    def __init__(self):
        super().__init__("stm32_serial_bridge")

        self.declare_parameter("serial_port", "/dev/rock64_stm32")
        self.declare_parameter("baud_rate", 115200)
        self.declare_parameter("max_speed", 255)
        self.declare_parameter("heartbeat_timeout", 0.5)
        self.declare_parameter("heartbeat_interval", 0.1)

        port = self.get_parameter("serial_port").value
        baud = self.get_parameter("baud_rate").value
        self._max = self.get_parameter("max_speed").value
        self._heartbeat_timeout = self.get_parameter("heartbeat_timeout").value
        self._heartbeat_interval = self.get_parameter("heartbeat_interval").value

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

    def _serial_read_loop(self):
        """Background thread to read heartbeat and ack messages from STM32."""
        while rclpy.ok() and self._ser and self._ser.is_open:
            try:
                if self._ser.in_waiting > 0:
                    line = self._ser.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        self._process_stm32_message(line)
                else:
                    time.sleep(0.01)
            except serial.SerialException as exc:
                self.get_logger().error(f"Serial read error: {exc}")
                break
            except Exception as exc:
                self.get_logger().error(f"Unexpected error in read loop: {exc}")
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
            if (current_time - self._last_heartbeat_time) > self._heartbeat_timeout:
                if self._stm32_alive:
                    self.get_logger().error("STM32 heartbeat timeout - motor commands disabled")
                    self._stm32_alive = False

        # Send heartbeat ping to STM32
        try:
            self._ser.write(b"PING\n")
        except serial.SerialException as exc:
            self.get_logger().warn(f"Heartbeat send failed: {exc}")

    def _cmd_vel_cb(self, msg: Twist):
        if self._ser is None or not self._ser.is_open:
            return

        # Check if STM32 is alive before sending commands
        with self._lock:
            if not self._stm32_alive:
                self.get_logger().warn("STM32 not responding - motor command dropped")
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
            # Reset acknowledgment flag - will be set when ACK received
            self._command_acknowledged = False
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
