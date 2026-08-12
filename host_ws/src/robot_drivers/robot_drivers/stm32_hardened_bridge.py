#!/usr/bin/env python3
# pylint: disable=import-error,no-name-in-module,no-member
# pylint: disable=broad-exception-caught
"""
Harden the packed-binary STM32 bridge with safety features.

Features:
- Robust binary frame parsing with circular buffer
- Asynchronous serial communication with non-blocking I/O
- Telemetry parsing (encoder, battery, IMU)
- Timeout-based failsafes and heartbeat monitoring
- Graceful port reconnection
- CRC-8 validation
- Proper endianness handling
- Thread-safe shared state
- Transition-gated logging to prevent spam
"""

import struct
import time
import threading
import queue
import math
from typing import Dict, Optional, Tuple, Union
from dataclasses import dataclass

import rclpy
import serial
from rclpy.node import Node
from rclpy.qos import (
    QoSDurabilityPolicy,
    QoSProfile,
    QoSReliabilityPolicy,
)
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool, Int32MultiArray, Empty
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from sensor_msgs.msg import BatteryState, Imu, JointState
from nav_msgs.msg import Odometry

# Protocol Constants
SYNC_1 = 0xAA
SYNC_2 = 0x55
FRAME_HEADER_SIZE = 4  # SYNC_1, SYNC_2, FUNC, LEN
FRAME_FOOTER_SIZE = 1  # CRC
MAX_FRAME_SIZE = 256
MAX_PAYLOAD_SIZE = MAX_FRAME_SIZE - FRAME_HEADER_SIZE - FRAME_FOOTER_SIZE
BUFFER_SIZE = 4096

# Function Codes
FUNC_SYS = 0x00
FUNC_MOTOR = 0x03
FUNC_ENCODER = 0x10
FUNC_BATTERY = 0x11
FUNC_IMU = 0x12
FUNC_SELF_TEST = 0x13
FUNC_HEARTBEAT = 0xF0
FUNC_ACK = 0xF1
FUNC_ERROR = 0xFF
VALID_FUNCTION_CODES = {
    FUNC_SYS,
    FUNC_MOTOR,
    FUNC_ENCODER,
    FUNC_BATTERY,
    FUNC_IMU,
    FUNC_SELF_TEST,
    FUNC_HEARTBEAT,
    FUNC_ACK,
    FUNC_ERROR,
}

# Motor Sub-commands
MOTOR_SUBCMD_SET_SPEED = 0x01
MOTOR_SUBCMD_EMERGENCY_STOP = 0x02

# Reflected CRC-8/MAXIM table retained for wire compatibility.
CRC8_TABLE = [
    0, 94, 188, 226, 97, 63, 221, 131, 194, 156, 126, 32, 163, 253, 31, 65,
    157, 195, 33, 127, 252, 162, 64, 30, 95, 1, 227, 189, 62, 96, 130, 220,
    35, 125, 159, 193, 66, 28, 254, 160, 225, 191, 93, 3, 128, 222, 60, 98,
    190, 224, 2, 92, 223, 129, 99, 61, 124, 34, 192, 158, 29, 67, 161, 255,
    70, 24, 250, 164, 39, 121, 155, 197, 132, 218, 56, 102, 229, 187, 89, 7,
    219, 133, 103, 57, 186, 228, 6, 88, 25, 71, 165, 251, 120, 38, 196, 154,
    101, 59, 217, 135, 4, 90, 184, 230, 167, 249, 27, 69, 198, 152, 122, 36,
    248, 166, 68, 26, 153, 199, 37, 123, 58, 100, 134, 216, 91, 5, 231, 185,
    140, 210, 48, 110, 237, 179, 81, 15, 78, 16, 242, 172, 47, 113, 147, 205,
    17, 79, 173, 243, 112, 46, 204, 146, 211, 141, 111, 49, 178, 236, 14, 80,
    175, 241, 19, 77, 206, 144, 114, 44, 109, 51, 209, 143, 12, 82, 176, 238,
    50, 108, 142, 208, 83, 13, 239, 177, 240, 174, 76, 18, 145, 207, 45, 115,
    202, 148, 118, 40, 171, 245, 23, 73, 8, 86, 180, 234, 105, 55, 213, 139,
    87, 9, 235, 181, 54, 104, 138, 212, 149, 203, 41, 119, 244, 170, 72, 22,
    233, 183, 85, 11, 136, 214, 52, 106, 43, 117, 151, 201, 74, 20, 246, 168,
    116, 42, 200, 150, 21, 75, 169, 247, 182, 232, 10, 84, 215, 137, 107, 53,
]


def crc8_ccitt(data: bytes) -> int:
    """Calculate the deployed reflected CRC-8 value."""
    crc = 0x00
    for byte in data:
        crc = CRC8_TABLE[crc ^ byte]
    return crc


@dataclass
class TelemetryData:
    """Container for telemetry data from STM32."""

    encoder_left: int = 0
    encoder_right: int = 0
    battery_voltage: float = 0.0
    battery_current: float = 0.0
    imu_accel: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    imu_gyro: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    timestamp: float = 0.0
    battery_received: bool = False  # Track if we've ever received a battery frame


class CircularBuffer:
    """Thread-safe circular buffer for serial data."""

    def __init__(self, size: int):
        self.buffer = bytearray(size)
        self.size = size
        self.write_pos = 0
        self.read_pos = 0
        self.lock = threading.Lock()
        self.count = 0

    def write(self, data: bytes) -> int:
        """Write data to buffer, returns number of bytes written."""
        with self.lock:
            bytes_written = 0
            for byte in data:
                if self.count < self.size:
                    self.buffer[self.write_pos] = byte
                    self.write_pos = (self.write_pos + 1) % self.size
                    self.count += 1
                    bytes_written += 1
                else:
                    break  # Buffer full
            return bytes_written

    def read(self, max_bytes: int) -> bytes:
        """Read up to max_bytes from buffer."""
        with self.lock:
            if self.count == 0:
                return b""

            bytes_to_read = min(max_bytes, self.count)
            result = bytearray(bytes_to_read)

            for i in range(bytes_to_read):
                result[i] = self.buffer[self.read_pos]
                self.read_pos = (self.read_pos + 1) % self.size
                self.count -= 1

            return bytes(result)

    def peek(self, max_bytes: int) -> bytes:
        """Peek at data without consuming it."""
        with self.lock:
            if self.count == 0:
                return b""

            bytes_to_peek = min(max_bytes, self.count)
            result = bytearray(bytes_to_peek)
            temp_pos = self.read_pos

            for i in range(bytes_to_peek):
                result[i] = self.buffer[temp_pos]
                temp_pos = (temp_pos + 1) % self.size

            return bytes(result)

    def clear(self):
        """Clear the buffer."""
        with self.lock:
            self.write_pos = 0
            self.read_pos = 0
            self.count = 0

    def available(self) -> int:
        """Return number of bytes available to read."""
        with self.lock:
            return self.count


class FrameParser:
    """Robust binary frame parser with sync detection and CRC validation."""

    def __init__(self):
        # 0: sync 1, 1: sync 2, 2: function, 3: length, 4: payload/CRC
        self.sync_state = 0
        self.expected_payload_len = 0
        self.frame_buffer = bytearray()
        self.parse_errors = 0
        self.valid_frames = 0
        self.crc_errors = 0
        self.sync_errors = 0
        self.malformed_frames = 0
        self.total_bytes_processed = 0
        self.lock = threading.RLock()

    def reset(self):
        """Reset parser state."""
        with self.lock:
            self.sync_state = 0
            self.expected_payload_len = 0
            self.frame_buffer.clear()
            # Don't reset error counters - they're cumulative for diagnostics

    def process_byte(self, byte: int) -> Optional[Tuple[int, bytes]]:
        """Process a single byte, return complete frame if available."""
        with self.lock:
            self.total_bytes_processed += 1

            if self.sync_state == 0:
                # Seeking SYNC_1
                if byte == SYNC_1:
                    self.sync_state = 1
                    self.frame_buffer = bytearray([SYNC_1])
                return None

            elif self.sync_state == 1:
                # Seeking SYNC_2
                if byte == SYNC_2:
                    self.sync_state = 2
                    self.frame_buffer.append(SYNC_2)
                else:
                    # False sync, reset
                    self.sync_errors += 1
                    if byte == SYNC_1:
                        self.frame_buffer = bytearray([SYNC_1])
                    else:
                        self.sync_state = 0
                        self.frame_buffer.clear()
                return None

            elif self.sync_state == 2:
                # Reading function code
                if byte not in VALID_FUNCTION_CODES:
                    self.parse_errors += 1
                    if byte == SYNC_1:
                        self.sync_state = 1
                        self.frame_buffer = bytearray([SYNC_1])
                    else:
                        self.sync_state = 0
                        self.frame_buffer.clear()
                    return None
                self.frame_buffer.append(byte)
                self.sync_state = 3
                return None

            elif self.sync_state == 3:
                # Reading payload length
                self.frame_buffer.append(byte)
                self.expected_payload_len = byte
                if self.expected_payload_len > MAX_PAYLOAD_SIZE:
                    self.malformed_frames += 1
                    self.sync_state = 0
                    self.expected_payload_len = 0
                    self.frame_buffer.clear()
                    return None
                if self.expected_payload_len == 0:
                    # No payload, read CRC
                    self.sync_state = 4
                else:
                    self.sync_state = 4  # Will read payload next
                return None

            elif self.sync_state == 4:
                # Reading payload or CRC
                self.frame_buffer.append(byte)

                # Check if we have header + payload
                current_len = len(self.frame_buffer)
                if (
                    current_len
                    >= FRAME_HEADER_SIZE + self.expected_payload_len
                ):
                    # Read CRC
                    if (
                        current_len
                        == FRAME_HEADER_SIZE
                        + self.expected_payload_len
                        + FRAME_FOOTER_SIZE
                    ):
                        # Complete frame, validate
                        frame = bytes(self.frame_buffer)
                        result = self._validate_frame(frame)
                        self.reset()
                        if result:
                            return result
                        else:
                            self.parse_errors += 1
                            return None
                return None

            return None

    def _validate_frame(self, frame: bytes) -> Optional[Tuple[int, bytes]]:
        """Validate frame CRC and return (function_code, payload)."""
        if len(frame) < FRAME_HEADER_SIZE + FRAME_FOOTER_SIZE:
            self.malformed_frames += 1
            return None

        # Extract components
        function_code = frame[2]
        payload_len = frame[3]
        payload = frame[4:4 + payload_len]
        received_crc = frame[4 + payload_len]

        # Calculate CRC
        body = frame[2:4 + payload_len]
        calculated_crc = self._crc8_ccitt(body)

        if received_crc != calculated_crc:
            self.crc_errors += 1
            return None

        self.valid_frames += 1
        return function_code, payload

    def _crc8_ccitt(self, data: bytes) -> int:
        """Calculate the deployed reflected CRC-8 value."""
        return crc8_ccitt(data)

    def get_stats(self) -> Dict[str, Union[int, float]]:
        """Get parser statistics."""
        with self.lock:
            total_frames = (
                self.valid_frames + self.crc_errors + self.malformed_frames
            )
            error_rate = (
                (self.crc_errors + self.malformed_frames)
                / max(1, total_frames)
                * 100
                if total_frames > 0
                else 0.0
            )

            return {
                "valid_frames": self.valid_frames,
                "parse_errors": self.parse_errors,
                "crc_errors": self.crc_errors,
                "sync_errors": self.sync_errors,
                "malformed_frames": self.malformed_frames,
                "total_bytes_processed": self.total_bytes_processed,
                "error_rate_percent": error_rate,
                "sync_state": self.sync_state,
            }


class STM32HardenedBridge(Node):
    """Industrial-grade STM32 bridge with comprehensive safety features."""

    def __init__(self):
        super().__init__("stm32_hardened_bridge")

        # Parameters
        self.declare_parameter("serial_port", "/dev/rock64_stm32")
        self.declare_parameter("baud_rate", 115200)  # 115200 baud to match STM32 USART1 (PA9/PA10)
        self.declare_parameter("max_speed", 255)
        self.declare_parameter("command_rate_hz", 50.0)
        self.declare_parameter("cmd_timeout", 0.25)
        self.declare_parameter("heartbeat_interval", 0.1)
        self.declare_parameter("heartbeat_timeout", 0.5)
        self.declare_parameter("reconnect_interval", 2.0)
        self.declare_parameter("linear_slew_rate", 3.0)
        self.declare_parameter("angular_slew_rate", 6.0)
        self.declare_parameter("encoder_timeout", 1.0)
        self.declare_parameter("enable_telemetry", True)
        self.declare_parameter("wheel_separation", 0.194)  # meters (track width)
        self.declare_parameter("wheel_radius", 0.065)  # meters
        self.declare_parameter("encoder_ticks_per_rev", 3960)  # 11 PPR * 4 edges * 90:1 gearbox
        self.declare_parameter("battery_min_voltage", 9.0)
        self.declare_parameter("battery_max_voltage", 12.0)
        self.declare_parameter("startup_grace_period", 2.0)

        # Get parameter values
        self._serial_port = self.get_parameter("serial_port").value
        self._baud_rate = self.get_parameter("baud_rate").value
        self._max_speed = int(self.get_parameter("max_speed").value)
        self._command_rate_hz = float(
            self.get_parameter("command_rate_hz").value
        )
        self._cmd_timeout = float(self.get_parameter("cmd_timeout").value)
        self._heartbeat_interval = float(
            self.get_parameter("heartbeat_interval").value
        )
        self._heartbeat_timeout = float(
            self.get_parameter("heartbeat_timeout").value
        )
        self._reconnect_interval = float(
            self.get_parameter("reconnect_interval").value
        )
        self._linear_slew_rate = float(
            self.get_parameter("linear_slew_rate").value
        )
        self._angular_slew_rate = float(
            self.get_parameter("angular_slew_rate").value
        )
        self._encoder_timeout = float(
            self.get_parameter("encoder_timeout").value
        )
        self._enable_telemetry = self.get_parameter("enable_telemetry").value
        self._wheel_separation = float(
            self.get_parameter("wheel_separation").value
        )
        self._wheel_radius = float(self.get_parameter("wheel_radius").value)
        self._encoder_ticks_per_rev = int(
            self.get_parameter("encoder_ticks_per_rev").value
        )
        self._battery_min_v = float(
            self.get_parameter("battery_min_voltage").value
        )
        self._battery_max_v = float(
            self.get_parameter("battery_max_voltage").value
        )
        self._startup_grace = float(
            self.get_parameter("startup_grace_period").value
        )

        # State variables — protected by _state_lock for thread safety
        self._state_lock = threading.Lock()
        self._target_lin = 0.0
        self._target_ang = 0.0
        self._cmd_lin = 0.0
        self._cmd_ang = 0.0
        self._last_cmd_vel_time = 0.0
        self._last_send_time = time.monotonic()
        self._last_sent_pair: Optional[Tuple[int, int]] = (None, None)
        self._last_heartbeat_time = 0.0
        self._last_encoder_time = 0.0
        self._connection_loss_time = 0.0
        self._reconnect_attempt_time = 0.0
        self._firmware_alive = False
        self._motion_armed = False
        self._estop_active = False  # Tracks whether we are currently in e-stop
        self._node_start_time = time.monotonic()

        # Odometry state
        self._odom_lock = threading.Lock()
        self._x = 0.0
        self._y = 0.0
        self._theta = 0.0
        self._prev_left_enc = 0
        self._prev_right_enc = 0
        self._prev_odom_time: Optional[float] = None

        # Telemetry data
        self._telemetry = TelemetryData()
        self._telemetry_lock = threading.Lock()

        # Serial communication
        self._ser: Optional[serial.Serial] = None
        self._serial_lock = threading.Lock()
        self._rx_buffer = CircularBuffer(BUFFER_SIZE)
        self._frame_parser = FrameParser()
        self._frame_queue: queue.Queue[Tuple[int, bytes]] = queue.Queue(
            maxsize=100
        )

        # Threading
        self._running = True
        self._read_thread: Optional[threading.Thread] = None
        self._process_thread: Optional[threading.Thread] = None

        # Initialize serial connection
        self._connect_serial()

        # ROS2 interfaces
        self._setup_ros_interfaces()

        # Diagnostic updater - use manual publishing for now
        self._diagnostic_updater = None
        self.get_logger().info("Using manual diagnostic publishing")

        # Timers
        self._setup_timers()

        self.get_logger().info("STM32 Hardened Bridge initialized")

    def _setup_ros_interfaces(self):
        """Set up ROS2 publishers and subscribers."""
        command_qos = QoSProfile(
            depth=1,
            reliability=QoSReliabilityPolicy.RELIABLE,
            durability=QoSDurabilityPolicy.VOLATILE,
        )
        self._cmd_vel_sub = self.create_subscription(
            Twist,
            "/ranger/cmd_vel_safe",
            self._cmd_vel_callback,
            command_qos,
        )

        # Publishers
        self._alive_pub = self.create_publisher(
            Bool, "/stm32/bridge_alive", 10
        )
        self._encoder_pub = self.create_publisher(
            Int32MultiArray, "/stm32/encoder_ticks", 10
        )
        self._joint_state_pub = self.create_publisher(
            JointState, "/stm32/joint_states", 10
        )
        self._battery_pub = self.create_publisher(
            BatteryState, "/stm32/battery", 10
        )
        self._imu_pub = self.create_publisher(Imu, "/stm32/imu", 10)
        self._odom_pub = self.create_publisher(Odometry, "/stm32/odom", 10)
        self._diagnostics_pub = self.create_publisher(
            DiagnosticArray, "/stm32/diagnostics", 10
        )
        self._self_test_result_pub = self.create_publisher(
            Bool, "/stm32/self_test_result", 10
        )
        self._self_test_trigger_sub = self.create_subscription(
            Empty, "/stm32/self_test", self._self_test_trigger_callback, 10
        )

    def _setup_timers(self):
        """Set up ROS2 timers."""
        # Command loop
        period = 1.0 / max(self._command_rate_hz, 1.0)
        self._command_timer = self.create_timer(period, self._command_loop)

        # Heartbeat
        self._heartbeat_timer = self.create_timer(
            self._heartbeat_interval, self._send_heartbeat
        )

        # Diagnostics
        self._diagnostics_timer = self.create_timer(
            0.5, self._publish_diagnostics
        )

        # Telemetry publishing
        if self._enable_telemetry:
            self._telemetry_timer = self.create_timer(
                0.1, self._publish_telemetry
            )

    def _connect_serial(self) -> bool:
        """Attempt to connect to serial port."""
        try:
            with self._serial_lock:
                if self._ser and self._ser.is_open:
                    self._ser.close()

                self._ser = serial.Serial(
                    self._serial_port,
                    self._baud_rate,
                    timeout=0.01,  # Non-blocking
                    write_timeout=0.1,
                )

                # Start background threads
                if (
                    self._read_thread is None
                    or not self._read_thread.is_alive()
                ):
                    self._read_thread = threading.Thread(
                        target=self._serial_read_loop, daemon=True
                    )
                    self._read_thread.start()

                if (
                    self._process_thread is None
                    or not self._process_thread.is_alive()
                ):
                    self._process_thread = threading.Thread(
                        target=self._frame_process_loop, daemon=True
                    )
                    self._process_thread.start()

                self._rx_buffer.clear()
                self._frame_parser.reset()

            with self._state_lock:
                self._connection_loss_time = 0.0
                self._target_lin = 0.0
                self._target_ang = 0.0
                self._cmd_lin = 0.0
                self._cmd_ang = 0.0
                self._last_cmd_vel_time = 0.0
                self._last_heartbeat_time = 0.0
                self._last_sent_pair = (None, None)
                self._firmware_alive = False
                self._motion_armed = False
                self._estop_active = False

            self.get_logger().info(
                f"Connected to {self._serial_port} @ {self._baud_rate}"
            )
            self._send_emergency_stop()  # Initial safety stop, not an emergency
            return True

        except serial.SerialException as e:
            self.get_logger().error(f"Serial connection failed: {e}")
            with self._state_lock:
                self._connection_loss_time = time.monotonic()
            return False

    def _serial_read_loop(self):
        """Background thread for non-blocking serial reads."""
        while self._running:
            try:
                if self._ser is None or not self._ser.is_open:
                    time.sleep(0.1)
                    continue

                # Non-blocking read
                if self._ser.in_waiting > 0:
                    data = self._ser.read(self._ser.in_waiting)
                    if data:
                        bytes_written = self._rx_buffer.write(data)
                        if bytes_written < len(data):
                            dropped = len(data) - bytes_written
                            self.get_logger().warn(
                                f"Serial buffer overflow, dropped {dropped} "
                                "bytes"
                            )
                else:
                    time.sleep(0.001)  # Short sleep when no data

            except serial.SerialException as e:
                self.get_logger().error(f"Serial read error: {e}")
                with self._state_lock:
                    self._connection_loss_time = time.monotonic()
                time.sleep(0.1)
            except Exception as e:
                self.get_logger().error(
                    f"Unexpected error in read loop: {e}"
                )
                time.sleep(0.1)

    def _frame_process_loop(self):
        """Background thread for frame parsing and processing."""
        while self._running:
            try:
                # Read available data from buffer
                data = self._rx_buffer.read(128)
                if not data:
                    time.sleep(0.001)
                    continue

                # Process each byte through frame parser
                for byte in data:
                    frame = self._frame_parser.process_byte(byte)
                    if frame:
                        function_code, payload = frame
                        try:
                            self._frame_queue.put(
                                (function_code, payload), timeout=0.01
                            )
                        except queue.Full:
                            self.get_logger().warn(
                                "Frame queue full, dropping frame"
                            )

            except Exception as e:
                self.get_logger().error(
                    f"Error in frame process loop: {e}"
                )
                time.sleep(0.01)

    def _cmd_vel_callback(self, msg: Twist):
        """Accept only finite velocity commands from the safety gateway."""
        linear = float(msg.linear.x)
        angular = float(msg.angular.z)
        if not (math.isfinite(linear) and math.isfinite(angular)):
            self.get_logger().error("Rejected non-finite safe velocity")
            with self._state_lock:
                self._target_lin = 0.0
                self._target_ang = 0.0
                self._motion_armed = False
            self._send_emergency_stop()
            return

        with self._state_lock:
            self._target_lin = linear
            self._target_ang = angular
            self._last_cmd_vel_time = time.monotonic()
            self._motion_armed = self._firmware_alive

    def _command_loop(self):
        """Run the command loop and enforce communication timeouts."""
        now = time.monotonic()

        # Check connection status and attempt reconnection
        if self._ser is None or not self._ser.is_open:
            with self._state_lock:
                reconnect_due = (
                    now - self._reconnect_attempt_time
                    > self._reconnect_interval
                )
            if reconnect_due:
                with self._state_lock:
                    self._reconnect_attempt_time = now
                if self._connect_serial():
                    self.get_logger().info("Serial reconnection successful")
            return

        # Process any queued frames before gating on heartbeat state.
        self._process_received_frames()

        with self._state_lock:
            heartbeat_age = now - self._last_heartbeat_time
            firmware_alive = self._firmware_alive
            motion_armed = self._motion_armed
            last_cmd_time = self._last_cmd_vel_time
            target_lin = self._target_lin
            target_ang = self._target_ang
            cmd_lin = self._cmd_lin
            cmd_ang = self._cmd_ang
            last_send = self._last_send_time
            last_sent = self._last_sent_pair
            estop_active = self._estop_active
            node_start = self._node_start_time

        # Startup grace period — don't enforce heartbeat until it expires
        in_grace = (now - node_start) < self._startup_grace

        heartbeat_expired = (
            not firmware_alive or heartbeat_age > self._heartbeat_timeout
        )

        if heartbeat_expired and not in_grace:
            if firmware_alive:
                self.get_logger().warn(
                    f"Heartbeat timeout: {heartbeat_age:.2f}s"
                )
            with self._state_lock:
                self._firmware_alive = False
                self._motion_armed = False
            if not estop_active:
                self._send_emergency_stop(emergency=True)  # Heartbeat timeout is an emergency
            else:
                self._send_emergency_stop(silent=True, emergency=True)
            return

        if not motion_armed:
            if not estop_active:
                self._send_emergency_stop()  # Not armed is not an emergency
            else:
                self._send_emergency_stop(silent=True)
            return

        # Check command timeout
        cmd_age = now - last_cmd_time
        stale = cmd_age > self._cmd_timeout

        if stale:
            # No recent commands, send stop (normal idle, not emergency)
            if not estop_active:
                self._send_emergency_stop()
            else:
                self._send_emergency_stop(silent=True)
            return

        # Apply slew rate limiting
        dt = now - last_send
        self._last_send_time = now

        new_lin = self._slew_limit(
            cmd_lin, target_lin, self._linear_slew_rate, dt
        )
        new_ang = self._slew_limit(
            cmd_ang, target_ang, self._angular_slew_rate, dt
        )

        with self._state_lock:
            self._cmd_lin = new_lin
            self._cmd_ang = new_ang

        # Convert to differential drive
        left_vel = new_lin - new_ang
        right_vel = new_lin + new_ang

        # Normalize to prevent saturation
        max_mag = max(1.0, abs(left_vel), abs(right_vel))
        left_vel /= max_mag
        right_vel /= max_mag

        # Convert to motor speeds
        left_speed = int(
            max(
                -self._max_speed,
                min(self._max_speed, left_vel * self._max_speed),
            )
        )
        right_speed = int(
            max(
                -self._max_speed,
                min(self._max_speed, right_vel * self._max_speed),
            )
        )

        # Send if changed
        if (left_speed, right_speed) != last_sent:
            self._send_motor_command(left_speed, right_speed)
            with self._state_lock:
                self._last_sent_pair = (left_speed, right_speed)
                # Clear e-stop latch whenever we successfully send motion commands
                self._estop_active = False
        else:
            # Even if speed unchanged, clear latch if we're actively commanding motion
            with self._state_lock:
                if (left_speed, right_speed) != (0, 0):
                    self._estop_active = False

    def _slew_limit(
        self, current: float, target: float, rate: float, dt: float
    ) -> float:
        """Apply slew rate limiting."""
        max_step = max(rate, 0.0) * max(dt, 0.0)
        delta = target - current
        if abs(delta) <= max_step:
            return target
        return current + math.copysign(max_step, delta)

    def _send_motor_command(self, left_speed: int, right_speed: int):
        """Send motor speed command to STM32."""
        left_rps = float(left_speed) / float(self._max_speed)
        right_rps = float(right_speed) / float(self._max_speed)

        payload = bytearray()
        payload.append(MOTOR_SUBCMD_SET_SPEED)
        payload.append(2)  # Number of motors
        payload.extend(struct.pack("<Bf", 0, left_rps))  # Motor 0 (left)
        payload.extend(struct.pack("<Bf", 1, right_rps))  # Motor 1 (right)

        self._send_frame(FUNC_MOTOR, bytes(payload))

    def _send_emergency_stop(self, silent: bool = False, emergency: bool = False):
        """Send emergency stop command.

        Args:
            silent: If True, do not emit a log message. Used to avoid
                spamming logs when the bridge remains in the stopped state.
            emergency: If True, this is an actual emergency condition, not just
                normal idle/timeout. Only set _estop_active latch for true emergencies.
        """
        if not silent:
            self.get_logger().warn("Sending emergency stop")
        self._send_frame(FUNC_MOTOR, bytes([MOTOR_SUBCMD_EMERGENCY_STOP, 0]))
        with self._state_lock:
            self._last_sent_pair = (0, 0)
            # Only latch e-stop state for actual emergencies, not normal idle/timeout
            if emergency:
                self._estop_active = True

    def _send_heartbeat(self):
        """Send heartbeat ping."""
        self._send_frame(FUNC_HEARTBEAT, b"")

    def trigger_self_test(self):
        """Trigger firmware self-test sequence."""
        self._send_frame(FUNC_SELF_TEST, b"")
        self.get_logger().info("Self-test triggered")

    def _self_test_trigger_callback(self, msg: Empty):
        """Callback for self-test trigger topic."""
        self.trigger_self_test()

    def _send_frame(self, function_code: int, payload: bytes = b""):
        """Send a complete frame with CRC."""
        if self._ser is None or not self._ser.is_open:
            return

        try:
            frame = self._build_frame(function_code, payload)
            with self._serial_lock:
                self._ser.write(frame)
        except serial.SerialException as e:
            self.get_logger().error(f"Serial write failed: {e}")
            with self._state_lock:
                self._connection_loss_time = time.monotonic()
                self._firmware_alive = False
                self._motion_armed = False

    def _build_frame(self, function_code: int, payload: bytes = b"") -> bytes:
        """Build a complete frame with header, payload, and CRC."""
        body = bytes([function_code, len(payload)]) + payload
        crc = self._crc8_ccitt(body)
        return bytes([SYNC_1, SYNC_2]) + body + bytes([crc])

    def _crc8_ccitt(self, data: bytes) -> int:
        """Calculate the deployed reflected CRC-8 value."""
        return crc8_ccitt(data)

    def _process_received_frames(self):
        """Process all pending frames from the queue."""
        try:
            while True:
                function_code, payload = self._frame_queue.get_nowait()
                self._handle_frame(function_code, payload)
        except queue.Empty:
            pass

    def _handle_frame(self, function_code: int, payload: bytes):
        """Handle a received frame based on function code."""
        try:
            if function_code == FUNC_HEARTBEAT:
                now = time.monotonic()
                with self._state_lock:
                    was_alive = self._firmware_alive
                    self._last_heartbeat_time = now
                    self._firmware_alive = True
                if not was_alive:
                    self.get_logger().info("STM32 heartbeat established")

            elif function_code == FUNC_ACK:
                self.get_logger().debug(f"Received ACK: {payload.hex()}")

            elif function_code == FUNC_ERROR:
                self.get_logger().error(
                    f"Received error from STM32: {payload.hex()}"
                )

            elif function_code == FUNC_ENCODER:
                self._parse_encoder_telemetry(payload)

            elif function_code == FUNC_BATTERY:
                self._parse_battery_telemetry(payload)

            elif function_code == FUNC_IMU:
                self._parse_imu_telemetry(payload)

            elif function_code == FUNC_SELF_TEST:
                self._parse_self_test_result(payload)

            else:
                self.get_logger().warn(
                    f"Unknown function code: 0x{function_code:02X}"
                )

        except Exception as e:
            self.get_logger().error(f"Error handling frame: {e}")

    def _parse_encoder_telemetry(self, payload: bytes):
        """Parse encoder telemetry payload."""
        if len(payload) < 8:
            self.get_logger().warn(
                f"Invalid encoder payload length: {len(payload)}"
            )
            return

        try:
            left_enc = struct.unpack("<i", payload[0:4])[0]
            right_enc = struct.unpack("<i", payload[4:8])[0]

            with self._telemetry_lock:
                self._telemetry.encoder_left = left_enc
                self._telemetry.encoder_right = right_enc
                self._telemetry.timestamp = time.monotonic()

            with self._state_lock:
                self._last_encoder_time = time.monotonic()

        except struct.error as e:
            self.get_logger().error(f"Error parsing encoder data: {e}")

    def _parse_battery_telemetry(self, payload: bytes):
        """Parse battery telemetry payload."""
        if len(payload) < 8:
            self.get_logger().warn(
                f"Invalid battery payload length: {len(payload)}"
            )
            return

        try:
            voltage = struct.unpack("<f", payload[0:4])[0]
            current = struct.unpack("<f", payload[4:8])[0]

            with self._telemetry_lock:
                self._telemetry.battery_voltage = voltage
                self._telemetry.battery_current = current
                self._telemetry.timestamp = time.monotonic()
                self._telemetry.battery_received = True

        except struct.error as e:
            self.get_logger().error(f"Error parsing battery data: {e}")

    def _parse_imu_telemetry(self, payload: bytes):
        """Parse IMU telemetry payload."""
        if len(payload) < 24:  # 3 accel + 3 gyro, each float32
            self.get_logger().warn(
                f"Invalid IMU payload length: {len(payload)}"
            )
            return

        try:
            accel_x = struct.unpack("<f", payload[0:4])[0]
            accel_y = struct.unpack("<f", payload[4:8])[0]
            accel_z = struct.unpack("<f", payload[8:12])[0]
            gyro_x = struct.unpack("<f", payload[12:16])[0]
            gyro_y = struct.unpack("<f", payload[16:20])[0]
            gyro_z = struct.unpack("<f", payload[20:24])[0]

            with self._telemetry_lock:
                self._telemetry.imu_accel = (accel_x, accel_y, accel_z)
                self._telemetry.imu_gyro = (gyro_x, gyro_y, gyro_z)
                self._telemetry.timestamp = time.monotonic()

        except struct.error as e:
            self.get_logger().error(f"Error parsing IMU data: {e}")

    def _parse_self_test_result(self, payload: bytes):
        """Parse self-test result payload."""
        if len(payload) < 4:  # status (1) + test_id (1) + error_code (2)
            self.get_logger().warn(
                f"Invalid self-test payload length: {len(payload)}"
            )
            return

        try:
            overall_status = struct.unpack("<B", payload[0:1])[0]
            test_id = struct.unpack("<B", payload[1:2])[0]
            error_code = struct.unpack("<H", payload[2:4])[0]

            # Map status codes to strings
            status_map = {0: "PASS", 1: "FAIL", 2: "RUNNING"}
            status_str = status_map.get(overall_status, "UNKNOWN")

            # Map test IDs to strings
            test_map = {
                0: "IDLE",
                1: "MOTOR_LEFT",
                2: "MOTOR_RIGHT",
                3: "ENCODER_LEFT",
                4: "ENCODER_RIGHT",
                5: "IMU",
                6: "BATTERY",
                7: "COMPLETE"
            }
            test_str = test_map.get(test_id, f"UNKNOWN({test_id})")

            if overall_status == 1:
                self.get_logger().error(
                    f"Self-test FAIL: {test_str} error_code=0x{error_code:04X}"
                )
            elif overall_status == 0:
                self.get_logger().info(f"Self-test PASS: {test_str}")
            else:
                self.get_logger().info(f"Self-test RUNNING: {test_str}")

            # Publish to self-test result topic
            from std_msgs.msg import Bool
            result_msg = Bool()
            result_msg.data = (overall_status == 0)
            self._self_test_result_pub.publish(result_msg)

        except struct.error as e:
            self.get_logger().error(f"Error parsing self-test data: {e}")

    def _publish_telemetry(self):
        """Publish telemetry data to ROS2 topics."""
        now = time.monotonic()

        # Copy telemetry under lock, then publish outside the lock
        with self._telemetry_lock:
            if now - self._telemetry.timestamp > self._encoder_timeout:
                return  # Stale data
            tel = TelemetryData(
                encoder_left=self._telemetry.encoder_left,
                encoder_right=self._telemetry.encoder_right,
                battery_voltage=self._telemetry.battery_voltage,
                battery_current=self._telemetry.battery_current,
                imu_accel=self._telemetry.imu_accel,
                imu_gyro=self._telemetry.imu_gyro,
                timestamp=self._telemetry.timestamp,
            )

        stamp = self.get_clock().now().to_msg()

        # Publish encoder data
        encoder_msg = Int32MultiArray()
        encoder_msg.data = [tel.encoder_left, tel.encoder_right]
        self._encoder_pub.publish(encoder_msg)

        # Publish joint states with velocity estimation
        joint_msg = JointState()
        joint_msg.header.stamp = stamp
        joint_msg.name = ["left_wheel_joint", "right_wheel_joint"]
        joint_msg.position = [
            float(tel.encoder_left),
            float(tel.encoder_right),
        ]

        # Compute wheel velocities from encoder deltas
        with self._odom_lock:
            prev_left = self._prev_left_enc
            prev_right = self._prev_right_enc
            prev_time = self._prev_odom_time

        if prev_time is not None:
            dt = tel.timestamp - prev_time
            if dt > 0.0:
                d_left = tel.encoder_left - prev_left
                d_right = tel.encoder_right - prev_right
                meters_per_tick = (
                    2.0 * math.pi * self._wheel_radius
                ) / float(self._encoder_ticks_per_rev)
                joint_msg.velocity = [
                    float(d_left) * meters_per_tick / dt,
                    float(d_right) * meters_per_tick / dt,
                ]
            else:
                joint_msg.velocity = [0.0, 0.0]
        else:
            joint_msg.velocity = [0.0, 0.0]

        self._joint_state_pub.publish(joint_msg)

        # Publish battery data
        if tel.battery_received:
            battery_msg = BatteryState()
            battery_msg.header.stamp = stamp
            battery_msg.voltage = tel.battery_voltage
            # Handle NaN from STM32 when current sensor is not available
            if math.isnan(tel.battery_current):
                battery_msg.current = 0.0
            else:
                battery_msg.current = tel.battery_current
            span = self._battery_max_v - self._battery_min_v
            if span > 0.0:
                battery_msg.percentage = min(
                    1.0,
                    max(
                        0.0,
                        (tel.battery_voltage - self._battery_min_v) / span,
                    ),
                )
            else:
                battery_msg.percentage = 0.0
            self._battery_pub.publish(battery_msg)

        # Publish IMU data
        if tel.imu_accel != (0.0, 0.0, 0.0):
            imu_msg = Imu()
            imu_msg.header.stamp = stamp
            imu_msg.header.frame_id = "imu_link"

            imu_msg.linear_acceleration.x = tel.imu_accel[0]
            imu_msg.linear_acceleration.y = tel.imu_accel[1]
            imu_msg.linear_acceleration.z = tel.imu_accel[2]

            imu_msg.angular_velocity.x = tel.imu_gyro[0]
            imu_msg.angular_velocity.y = tel.imu_gyro[1]
            imu_msg.angular_velocity.z = tel.imu_gyro[2]

            self._imu_pub.publish(imu_msg)

        # Calculate and publish odometry
        self._update_odometry(tel)

    def _update_odometry(self, tel: TelemetryData):
        """Calculate and publish differential drive odometry from encoders."""
        left_enc = tel.encoder_left
        right_enc = tel.encoder_right
        now = tel.timestamp

        with self._odom_lock:
            prev_left = self._prev_left_enc
            prev_right = self._prev_right_enc
            prev_time = self._prev_odom_time

            # Update stored encoders immediately
            self._prev_left_enc = left_enc
            self._prev_right_enc = right_enc
            self._prev_odom_time = now

        if prev_time is None:
            # First sample — nothing to differentiate yet
            return

        # Calculate delta ticks
        d_left = left_enc - prev_left
        d_right = right_enc - prev_right

        # Convert ticks to distance (meters)
        meters_per_tick = (2.0 * math.pi * self._wheel_radius) / float(
            self._encoder_ticks_per_rev
        )
        dist_left = float(d_left) * meters_per_tick
        dist_right = float(d_right) * meters_per_tick

        d_center = (dist_left + dist_right) / 2.0
        d_theta = (dist_right - dist_left) / self._wheel_separation

        # Use actual elapsed time for velocity, not a hardcoded constant
        dt = now - prev_time
        if dt <= 0.0:
            return

        with self._odom_lock:
            # Update pose
            self._x += d_center * math.cos(self._theta + d_theta / 2.0)
            self._y += d_center * math.sin(self._theta + d_theta / 2.0)
            self._theta += d_theta
            self._theta = math.atan2(
                math.sin(self._theta), math.cos(self._theta)
            )

            x = self._x
            y = self._y
            theta = self._theta

        # Quaternion from yaw
        q_x, q_y, q_z, q_w = self._yaw_to_quaternion(theta)

        # Publish odometry message
        odom_msg = Odometry()
        odom_msg.header.stamp = self.get_clock().now().to_msg()
        odom_msg.header.frame_id = "odom"
        odom_msg.child_frame_id = "base_link"

        odom_msg.pose.pose.position.x = x
        odom_msg.pose.pose.position.y = y
        odom_msg.pose.pose.position.z = 0.0
        odom_msg.pose.pose.orientation.x = q_x
        odom_msg.pose.pose.orientation.y = q_y
        odom_msg.pose.pose.orientation.z = q_z
        odom_msg.pose.pose.orientation.w = q_w

        odom_msg.twist.twist.linear.x = d_center / dt
        odom_msg.twist.twist.angular.z = d_theta / dt

        self._odom_pub.publish(odom_msg)

    def _yaw_to_quaternion(
        self, yaw: float
    ) -> Tuple[float, float, float, float]:
        """Convert yaw angle to quaternion components (x, y, z, w)."""
        qz = math.sin(yaw / 2.0)
        qw = math.cos(yaw / 2.0)
        return 0.0, 0.0, qz, qw

    def _publish_diagnostics(self):
        """Publish system diagnostics and bridge status."""
        diag_array = DiagnosticArray()
        diag_array.header.stamp = self.get_clock().now().to_msg()

        status = DiagnosticStatus()
        status.name = "stm32_hardened_bridge: Serial Link"

        if self._ser and self._ser.is_open:
            status.level = DiagnosticStatus.OK
            status.message = "Connected"
        else:
            status.level = DiagnosticStatus.ERROR
            status.message = "Disconnected"

        stats = self._frame_parser.get_stats()
        for k, v in stats.items():
            status.values.append(KeyValue(key=k, value=str(v)))

        with self._state_lock:
            status.values.append(
                KeyValue(key="firmware_alive", value=str(self._firmware_alive))
            )
            status.values.append(
                KeyValue(key="motion_armed", value=str(self._motion_armed))
            )
            status.values.append(
                KeyValue(key="estop_active", value=str(self._estop_active))
            )

        diag_array.status.append(status)
        self._diagnostics_pub.publish(diag_array)

        # Publish bridge alive status
        alive_msg = Bool()
        alive_msg.data = self._ser is not None and self._ser.is_open
        self._alive_pub.publish(alive_msg)

    def destroy_node(self):
        """Clean shutdown of background threads and serial port."""
        self._running = False

        # Cancel ROS2 timers first to stop callbacks during teardown
        for timer_attr in (
            "_command_timer",
            "_heartbeat_timer",
            "_diagnostics_timer",
            "_telemetry_timer",
        ):
            timer = getattr(self, timer_attr, None)
            if timer is not None:
                timer.cancel()

        if self._read_thread and self._read_thread.is_alive():
            self._read_thread.join(timeout=1.0)
        if self._process_thread and self._process_thread.is_alive():
            self._process_thread.join(timeout=1.0)

        with self._serial_lock:
            if self._ser and self._ser.is_open:
                self._ser.close()

        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    bridge = STM32HardenedBridge()
    try:
        rclpy.spin(bridge)
    except KeyboardInterrupt:
        pass
    finally:
        bridge.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()