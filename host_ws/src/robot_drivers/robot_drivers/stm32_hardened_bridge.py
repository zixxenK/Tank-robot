#!/usr/bin/env python3
"""stm32_hardened_bridge.py - Industrial-grade STM32 binary bridge with safety features.

Features:
- Robust binary frame parsing with circular buffer
- Asynchronous serial communication with non-blocking I/O
- Telemetry parsing (encoder, battery, IMU)
- Timeout-based failsafes and heartbeat monitoring
- Graceful port reconnection
- CRC-8 validation
- Proper endianness handling
"""

import struct
import time
import threading
import queue
import math
from typing import Optional, Tuple, Callable, Dict, Any
from collections import deque
from dataclasses import dataclass

import rclpy
import serial
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool, Int32MultiArray, Float32MultiArray
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from sensor_msgs.msg import BatteryState, Imu, JointState
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Quaternion

# Protocol Constants
SYNC_1 = 0xAA
SYNC_2 = 0x55
FRAME_HEADER_SIZE = 4  # SYNC_1, SYNC_2, FUNC, LEN
FRAME_FOOTER_SIZE = 1  # CRC
MAX_FRAME_SIZE = 256
BUFFER_SIZE = 4096

# Function Codes
FUNC_SYS = 0x00
FUNC_MOTOR = 0x03
FUNC_ENCODER = 0x10
FUNC_BATTERY = 0x11
FUNC_IMU = 0x12
FUNC_HEARTBEAT = 0xF0
FUNC_ACK = 0xF1
FUNC_ERROR = 0xFF

# Motor Sub-commands
MOTOR_SUBCMD_SET_SPEED = 0x01
MOTOR_SUBCMD_EMERGENCY_STOP = 0x02

# CRC-8-CCITT Table
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
                return b''
            
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
                return b''
            
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
        self.sync_state = 0  # 0: seeking SYNC_1, 1: seeking SYNC_2, 2: reading header, 3: reading payload
        self.expected_payload_len = 0
        self.frame_buffer = bytearray()
        self.parse_errors = 0
        self.valid_frames = 0
        self.crc_errors = 0
        self.sync_errors = 0
        self.malformed_frames = 0
        self.total_bytes_processed = 0
        self.lock = threading.Lock()

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
                self.frame_buffer.append(byte)
                self.sync_state = 3
                return None
            
            elif self.sync_state == 3:
                # Reading payload length
                self.frame_buffer.append(byte)
                self.expected_payload_len = byte
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
                if current_len >= FRAME_HEADER_SIZE + self.expected_payload_len:
                    # Read CRC
                    if current_len == FRAME_HEADER_SIZE + self.expected_payload_len + FRAME_FOOTER_SIZE:
                        # Complete frame, validate
                        frame = bytes(self.frame_buffer)
                        result = self._validate_frame(frame)
                        self.reset()
                        if result:
                            self.valid_frames += 1
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
        payload = frame[4:4+payload_len]
        received_crc = frame[4+payload_len]

        # Calculate CRC
        body = frame[2:4+payload_len]  # function_code + payload_len + payload
        calculated_crc = self._crc8_ccitt(body)

        if received_crc != calculated_crc:
            self.crc_errors += 1
            return None

        self.valid_frames += 1
        return function_code, payload

    def _crc8_ccitt(self, data: bytes) -> int:
        """Calculate CRC-8-CCITT."""
        crc = 0x00
        for byte in data:
            crc = CRC8_TABLE[crc ^ byte]
        return crc

    def get_stats(self) -> Dict[str, int]:
        """Get parser statistics."""
        with self.lock:
            total_frames = self.valid_frames + self.crc_errors + self.malformed_frames
            error_rate = (self.crc_errors + self.malformed_frames) / max(1, total_frames) * 100 if total_frames > 0 else 0.0

            return {
                'valid_frames': self.valid_frames,
                'crc_errors': self.crc_errors,
                'sync_errors': self.sync_errors,
                'malformed_frames': self.malformed_frames,
                'total_bytes_processed': self.total_bytes_processed,
                'error_rate_percent': error_rate,
                'sync_state': self.sync_state
            }


class STM32HardenedBridge(Node):
    """Industrial-grade STM32 bridge with comprehensive safety features."""

    def __init__(self):
        super().__init__("stm32_hardened_bridge")

        # Parameters
        self.declare_parameter("serial_port", "/dev/rock64_stm32")
        self.declare_parameter("baud_rate", 115200)
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
        self.declare_parameter("wheel_separation", 0.3)  # meters
        self.declare_parameter("wheel_radius", 0.06)    # meters
        self.declare_parameter("encoder_ticks_per_rev", 1000)

        # Get parameter values
        self._serial_port = self.get_parameter("serial_port").value
        self._baud_rate = self.get_parameter("baud_rate").value
        self._max_speed = int(self.get_parameter("max_speed").value)
        self._command_rate_hz = float(self.get_parameter("command_rate_hz").value)
        self._cmd_timeout = float(self.get_parameter("cmd_timeout").value)
        self._heartbeat_interval = float(self.get_parameter("heartbeat_interval").value)
        self._heartbeat_timeout = float(self.get_parameter("heartbeat_timeout").value)
        self._reconnect_interval = float(self.get_parameter("reconnect_interval").value)
        self._linear_slew_rate = float(self.get_parameter("linear_slew_rate").value)
        self._angular_slew_rate = float(self.get_parameter("angular_slew_rate").value)
        self._encoder_timeout = float(self.get_parameter("encoder_timeout").value)
        self._enable_telemetry = self.get_parameter("enable_telemetry").value
        self._wheel_separation = float(self.get_parameter("wheel_separation").value)
        self._wheel_radius = float(self.get_parameter("wheel_radius").value)
        self._encoder_ticks_per_rev = int(self.get_parameter("encoder_ticks_per_rev").value)

        # State variables
        self._target_lin = 0.0
        self._target_ang = 0.0
        self._cmd_lin = 0.0
        self._cmd_ang = 0.0
        self._last_cmd_vel_time = time.time()
        self._last_send_time = time.time()
        self._last_sent_pair = (None, None)
        self._last_heartbeat_time = 0.0
        self._last_encoder_time = 0.0
        self._connection_loss_time = 0.0
        self._reconnect_attempt_time = 0.0

        # Odometry state
        self._x = 0.0
        self._y = 0.0
        self._theta = 0.0
        self._prev_left_enc = 0
        self._prev_right_enc = 0

        # Telemetry data
        self._telemetry = TelemetryData()
        self._telemetry_lock = threading.Lock()

        # Serial communication
        self._ser: Optional[serial.Serial] = None
        self._serial_lock = threading.Lock()
        self._rx_buffer = CircularBuffer(BUFFER_SIZE)
        self._frame_parser = FrameParser()
        self._frame_queue = queue.Queue(maxsize=100)

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
        """Setup ROS2 publishers and subscribers."""
        # Subscribers
        self._cmd_vel_sub = self.create_subscription(
            Twist, "/cmd_vel", self._cmd_vel_callback, 10
        )
        
        # Motor command subscriber (from ranger_base_node)
        self._motor_cmd_sub = self.create_subscription(
            Float32MultiArray, "/stm32/motor_commands", self._motor_cmd_callback, 10
        )

        # Publishers
        self._alive_pub = self.create_publisher(Bool, "/stm32/bridge_alive", 10)
        self._encoder_pub = self.create_publisher(Int32MultiArray, "/stm32/encoder_ticks", 10)
        self._joint_state_pub = self.create_publisher(JointState, "/stm32/joint_states", 10)
        self._battery_pub = self.create_publisher(BatteryState, "/stm32/battery", 10)
        self._imu_pub = self.create_publisher(Imu, "/stm32/imu", 10)
        self._odom_pub = self.create_publisher(Odometry, "/stm32/odom", 10)
        self._diagnostics_pub = self.create_publisher(DiagnosticArray, "/stm32/diagnostics", 10)

    def _setup_timers(self):
        """Setup ROS2 timers."""
        # Command loop
        period = 1.0 / max(self._command_rate_hz, 1.0)
        self._command_timer = self.create_timer(period, self._command_loop)

        # Heartbeat
        self._heartbeat_timer = self.create_timer(
            self._heartbeat_interval, self._send_heartbeat
        )

        # Diagnostics
        self._diagnostics_timer = self.create_timer(0.5, self._publish_diagnostics)

        # Telemetry publishing
        if self._enable_telemetry:
            self._telemetry_timer = self.create_timer(0.1, self._publish_telemetry)

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
                    write_timeout=0.1
                )
                
                # Start background threads
                if self._read_thread is None or not self._read_thread.is_alive():
                    self._read_thread = threading.Thread(
                        target=self._serial_read_loop, daemon=True
                    )
                    self._read_thread.start()
                
                if self._process_thread is None or not self._process_thread.is_alive():
                    self._process_thread = threading.Thread(
                        target=self._frame_process_loop, daemon=True
                    )
                    self._process_thread.start()
                
                self._rx_buffer.clear()
                self._frame_parser.reset()
                self._connection_loss_time = 0.0
                
                self.get_logger().info(
                    f"Connected to {self._serial_port} @ {self._baud_rate}"
                )
                return True
                
        except serial.SerialException as e:
            self.get_logger().error(f"Serial connection failed: {e}")
            self._connection_loss_time = time.time()
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
                            self.get_logger().warn(
                                f"Serial buffer overflow, dropped {len(data) - bytes_written} bytes"
                            )
                else:
                    time.sleep(0.001)  # Short sleep when no data
                    
            except serial.SerialException as e:
                self.get_logger().error(f"Serial read error: {e}")
                self._connection_loss_time = time.time()
                time.sleep(0.1)
            except Exception as e:
                self.get_logger().error(f"Unexpected error in read loop: {e}")
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
                            self._frame_queue.put((function_code, payload), timeout=0.01)
                        except queue.Full:
                            self.get_logger().warn("Frame queue full, dropping frame")
                            
            except Exception as e:
                self.get_logger().error(f"Error in frame process loop: {e}")
                time.sleep(0.01)

    def _cmd_vel_callback(self, msg: Twist):
        """Handle cmd_vel messages."""
        self._target_lin = float(msg.linear.x)
        self._target_ang = float(msg.angular.z)
        self._last_cmd_vel_time = time.time()

    def _motor_cmd_callback(self, msg: Float32MultiArray):
        """Handle motor command messages from ranger_base_node."""
        # Format: [motor_id_0, rps_0, motor_id_1, rps_1, ...]
        if len(msg.data) >= 4:
            motor_id_0 = int(msg.data[0])
            rps_0 = float(msg.data[1])
            motor_id_1 = int(msg.data[2])
            rps_1 = float(msg.data[3])
            
            # Store for drive loop
            self._vendor_motor_entries = [
                (motor_id_0, rps_0),
                (motor_id_1, rps_1)
            ]
            self._vendor_motor_timestamp = time.time()
            self._last_cmd_vel_time = time.time()

    def _command_loop(self):
        """Main command loop - sends motor commands and handles timeouts."""
        now = time.time()

        # Check connection status and attempt reconnection
        if self._ser is None or not self._ser.is_open:
            if now - self._reconnect_attempt_time > self._reconnect_interval:
                self._reconnect_attempt_time = now
                if self._connect_serial():
                    self.get_logger().info("Serial reconnection successful")
            return

        # Check heartbeat timeout
        if self._last_heartbeat_time > 0:
            heartbeat_age = now - self._last_heartbeat_time
            if heartbeat_age > self._heartbeat_timeout:
                self.get_logger().warn(f"Heartbeat timeout: {heartbeat_age:.2f}s")
                self._send_emergency_stop()
                # Don't return - continue trying to communicate

        # Check command timeout
        cmd_age = now - self._last_cmd_vel_time
        stale = cmd_age > self._cmd_timeout
        
        if stale:
            # No recent commands, send stop
            self._send_emergency_stop()
            return

        # Prefer direct motor commands from ranger_base_node
        if (
            self._vendor_motor_entries
            and (now - self._vendor_motor_timestamp) <= self._cmd_timeout
        ):
            # Send motor commands directly from ranger_base_node
            for motor_id, rps in self._vendor_motor_entries:
                self._send_motor_rps_command(motor_id, rps)
            self._last_sent_pair = (None, None)  # Reset to allow re-sending
            return

        # Fallback to cmd_vel processing (if no direct motor commands)
        # Apply slew rate limiting
        dt = now - self._last_send_time
        self._last_send_time = now
        
        self._cmd_lin = self._slew_limit(
            self._cmd_lin, self._target_lin, self._linear_slew_rate, dt
        )
        self._cmd_ang = self._slew_limit(
            self._cmd_ang, self._target_ang, self._angular_slew_rate, dt
        )

        # Convert to differential drive
        left_vel = self._cmd_lin - self._cmd_ang
        right_vel = self._cmd_lin + self._cmd_ang
        
        # Normalize to prevent saturation
        max_mag = max(1.0, abs(left_vel), abs(right_vel))
        left_vel /= max_mag
        right_vel /= max_mag

        # Convert to motor speeds
        left_speed = int(max(-self._max_speed, min(self._max_speed, left_vel * self._max_speed)))
        right_speed = int(max(-self._max_speed, min(self._max_speed, right_vel * self._max_speed)))

        # Send if changed
        if (left_speed, right_speed) != self._last_sent_pair:
            self._send_motor_command(left_speed, right_speed)
            self._last_sent_pair = (left_speed, right_speed)

        # Process received frames
        self._process_received_frames()

    def _slew_limit(self, current: float, target: float, rate: float, dt: float) -> float:
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

    def _send_motor_rps_command(self, motor_id: int, rps: float):
        """Send direct motor RPS command from ranger_base_node."""
        payload = bytearray()
        payload.append(MOTOR_SUBCMD_SET_SPEED)
        payload.append(1)  # Single motor
        payload.extend(struct.pack("<Bf", motor_id, rps))
        self._send_frame(FUNC_MOTOR, bytes(payload))

    def _send_emergency_stop(self):
        """Send emergency stop command."""
        self.get_logger().warn("Sending emergency stop")
        self._send_frame(FUNC_MOTOR, bytes([MOTOR_SUBCMD_EMERGENCY_STOP, 0]))
        self._last_sent_pair = (0, 0)

    def _send_heartbeat(self):
        """Send heartbeat ping."""
        self._send_frame(FUNC_HEARTBEAT, b"")

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
            self._connection_loss_time = time.time()

    def _build_frame(self, function_code: int, payload: bytes = b"") -> bytes:
        """Build a complete frame with header, payload, and CRC."""
        body = bytes([function_code, len(payload)]) + payload
        crc = self._crc8_ccitt(body)
        return bytes([SYNC_1, SYNC_2]) + body + bytes([crc])

    def _crc8_ccitt(self, data: bytes) -> int:
        """Calculate CRC-8-CCITT."""
        crc = 0x00
        for byte in data:
            crc = CRC8_TABLE[crc ^ byte]
        return crc

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
                self._last_heartbeat_time = time.time()
                
            elif function_code == FUNC_ACK:
                self.get_logger().debug(f"Received ACK: {payload.hex()}")
                
            elif function_code == FUNC_ERROR:
                self.get_logger().error(f"Received error from STM32: {payload.hex()}")
                
            elif function_code == FUNC_ENCODER:
                self._parse_encoder_telemetry(payload)
                
            elif function_code == FUNC_BATTERY:
                self._parse_battery_telemetry(payload)
                
            elif function_code == FUNC_IMU:
                self._parse_imu_telemetry(payload)
                
            else:
                self.get_logger().warn(f"Unknown function code: 0x{function_code:02X}")
                
        except Exception as e:
            self.get_logger().error(f"Error handling frame: {e}")

    def _parse_encoder_telemetry(self, payload: bytes):
        """Parse encoder telemetry payload."""
        if len(payload) < 8:
            self.get_logger().warn(f"Invalid encoder payload length: {len(payload)}")
            return
        
        try:
            left_enc = struct.unpack("<i", payload[0:4])[0]
            right_enc = struct.unpack("<i", payload[4:8])[0]
            
            with self._telemetry_lock:
                self._telemetry.encoder_left = left_enc
                self._telemetry.encoder_right = right_enc
                self._telemetry.timestamp = time.time()
            
            self._last_encoder_time = time.time()
            
        except struct.error as e:
            self.get_logger().error(f"Error parsing encoder data: {e}")

    def _parse_battery_telemetry(self, payload: bytes):
        """Parse battery telemetry payload."""
        if len(payload) < 8:
            self.get_logger().warn(f"Invalid battery payload length: {len(payload)}")
            return
        
        try:
            voltage = struct.unpack("<f", payload[0:4])[0]
            current = struct.unpack("<f", payload[4:8])[0]
            
            with self._telemetry_lock:
                self._telemetry.battery_voltage = voltage
                self._telemetry.battery_current = current
                self._telemetry.timestamp = time.time()
                
        except struct.error as e:
            self.get_logger().error(f"Error parsing battery data: {e}")

    def _parse_imu_telemetry(self, payload: bytes):
        """Parse IMU telemetry payload."""
        if len(payload) < 24:  # 3 accel + 3 gyro, each float32
            self.get_logger().warn(f"Invalid IMU payload length: {len(payload)}")
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
                self._telemetry.timestamp = time.time()
                
        except struct.error as e:
            self.get_logger().error(f"Error parsing IMU data: {e}")

    def _publish_telemetry(self):
        """Publish telemetry data to ROS2 topics."""
        now = time.time()
        
        with self._telemetry_lock:
            # Check if telemetry is fresh
            if now - self._telemetry.timestamp > self._encoder_timeout:
                return  # Stale data
            
            # Publish encoder data
            encoder_msg = Int32MultiArray()
            encoder_msg.data = [self._telemetry.encoder_left, self._telemetry.encoder_right]
            self._encoder_pub.publish(encoder_msg)
            
            # Publish joint states
            joint_msg = JointState()
            joint_msg.header.stamp = self.get_clock().now().to_msg()
            joint_msg.name = ["left_wheel_joint", "right_wheel_joint"]
            joint_msg.position = [float(self._telemetry.encoder_left), float(self._telemetry.encoder_right)]
            joint_msg.velocity = [0.0, 0.0]  # Would need to calculate from delta
            self._joint_state_pub.publish(joint_msg)
            
            # Publish battery data
            if self._telemetry.battery_voltage > 0:
                battery_msg = BatteryState()
                battery_msg.header.stamp = self.get_clock().now().to_msg()
                battery_msg.voltage = self._telemetry.battery_voltage
                battery_msg.current = self._telemetry.battery_current
                battery_msg.percentage = min(1.0, max(0.0, (self._telemetry.battery_voltage - 9.0) / 3.0))
                self._battery_pub.publish(battery_msg)
            
            # Publish IMU data
            if self._telemetry.imu_accel != (0.0, 0.0, 0.0):
                imu_msg = Imu()
                imu_msg.header.stamp = self.get_clock().now().to_msg()
                imu_msg.linear_acceleration.x = self._telemetry.imu_accel[0]
                imu_msg.linear_acceleration.y = self._telemetry.imu_accel[1]
                imu_msg.linear_acceleration.z = self._telemetry.imu_accel[2]
                imu_msg.angular_velocity.x = self._telemetry.imu_gyro[0]
                imu_msg.angular_velocity.y = self._telemetry.imu_gyro[1]
                imu_msg.angular_velocity.z = self._telemetry.imu_gyro[2]
                self._imu_pub.publish(imu_msg)

            # Publish odometry from encoder data
            self._publish_odometry()

    def _publish_odometry(self):
        """Publish odometry from encoder data using differential drive kinematics."""
        with self._telemetry_lock:
            left_enc = self._telemetry.encoder_left
            right_enc = self._telemetry.encoder_right
            timestamp = self._telemetry.timestamp

        # Calculate delta in encoder ticks
        delta_left = left_enc - self._prev_left_enc
        delta_right = right_enc - self._prev_right_enc

        # Convert ticks to distance (meters)
        ticks_per_meter = self._encoder_ticks_per_rev / (2 * math.pi * self._wheel_radius)
        left_dist = delta_left / ticks_per_meter
        right_dist = delta_right / ticks_per_meter

        # Differential drive kinematics
        dist = (left_dist + right_dist) / 2.0
        delta_theta = (right_dist - left_dist) / self._wheel_separation

        # Update pose
        self._x += dist * math.cos(self._theta)
        self._y += dist * math.sin(self._theta)
        self._theta += delta_theta

        # Calculate velocities
        dt = timestamp - (self._last_encoder_time if self._last_encoder_time > 0 else timestamp)
        if dt > 0:
            linear_vel = dist / dt
            angular_vel = delta_theta / dt
        else:
            linear_vel = 0.0
            angular_vel = 0.0

        # Create odometry message
        odom_msg = Odometry()
        odom_msg.header.stamp = self.get_clock().now().to_msg()
        odom_msg.header.frame_id = "odom"
        odom_msg.child_frame_id = "base_link"

        # Position
        odom_msg.pose.pose.position.x = self._x
        odom_msg.pose.pose.position.y = self._y
        odom_msg.pose.pose.position.z = 0.0

        # Orientation from yaw
        quat = self._yaw_to_quaternion(self._theta)
        odom_msg.pose.pose.orientation = quat

        # Velocity (in child frame)
        odom_msg.twist.twist.linear.x = linear_vel
        odom_msg.twist.twist.linear.y = 0.0
        odom_msg.twist.twist.angular.z = angular_vel

        # Publish
        self._odom_pub.publish(odom_msg)

        # Update previous encoder values
        self._prev_left_enc = left_enc
        self._prev_right_enc = right_enc

    def _yaw_to_quaternion(self, yaw: float):
        """Convert yaw angle to quaternion."""
        quat = Quaternion()
        quat.x = 0.0
        quat.y = 0.0
        quat.z = math.sin(yaw / 2.0)
        quat.w = math.cos(yaw / 2.0)
        return quat

    def _publish_diagnostics(self):
        """Publish diagnostic information."""
        now = time.time()

        # Connection status
        serial_open = bool(self._ser and self._ser.is_open)
        alive = serial_open and (now - self._last_heartbeat_time) < self._heartbeat_timeout

        # Frame parser stats
        parser_stats = self._frame_parser.get_stats()

        # Buffer status
        buffer_available = self._rx_buffer.available()

        # Create diagnostic status
        status = DiagnosticStatus()
        status.name = "stm32_hardened_bridge"
        status.hardware_id = self._serial_port

        if not serial_open:
            status.level = DiagnosticStatus.ERROR
            status.message = "serial_closed"
        elif not alive:
            status.level = DiagnosticStatus.ERROR
            status.message = "heartbeat_timeout"
        elif parser_stats['error_rate_percent'] > 5.0:
            status.level = DiagnosticStatus.WARN
            status.message = f"high_error_rate_{parser_stats['error_rate_percent']:.1f}%"
        elif parser_stats['crc_errors'] > 10:
            status.level = DiagnosticStatus.WARN
            status.message = f"crc_errors_{parser_stats['crc_errors']}"
        else:
            status.level = DiagnosticStatus.OK
            status.message = "ok"

        status.values = [
            KeyValue(key="serial_open", value=str(serial_open).lower()),
            KeyValue(key="alive", value=str(alive).lower()),
            KeyValue(key="heartbeat_age_s", value=f"{now - self._last_heartbeat_time:.3f}"),
            KeyValue(key="valid_frames", value=str(parser_stats['valid_frames'])),
            KeyValue(key="crc_errors", value=str(parser_stats['crc_errors'])),
            KeyValue(key="sync_errors", value=str(parser_stats['sync_errors'])),
            KeyValue(key="malformed_frames", value=str(parser_stats['malformed_frames'])),
            KeyValue(key="error_rate_percent", value=f"{parser_stats['error_rate_percent']:.2f}"),
            KeyValue(key="total_bytes", value=str(parser_stats['total_bytes_processed'])),
            KeyValue(key="buffer_available", value=str(buffer_available)),
            KeyValue(key="encoder_left", value=str(self._telemetry.encoder_left)),
            KeyValue(key="encoder_right", value=str(self._telemetry.encoder_right)),
            KeyValue(key="battery_voltage", value=f"{self._telemetry.battery_voltage:.2f}"),
        ]

        diag_msg = DiagnosticArray()
        diag_msg.header.stamp = self.get_clock().now().to_msg()
        diag_msg.status = [status]
        self._diagnostics_pub.publish(diag_msg)

        # Publish alive status
        self._alive_pub.publish(Bool(data=alive))

    def destroy_node(self):
        """Cleanup and shutdown."""
        self.get_logger().info("Shutting down STM32 Hardened Bridge")
        
        self._running = False
        
        # Send emergency stop before closing
        if self._ser and self._ser.is_open:
            self._send_emergency_stop()
            time.sleep(0.1)  # Give it time to send
            self._ser.close()
        
        # Wait for threads to finish
        if self._read_thread and self._read_thread.is_alive():
            self._read_thread.join(timeout=1.0)
        if self._process_thread and self._process_thread.is_alive():
            self._process_thread.join(timeout=1.0)
        
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = STM32HardenedBridge()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
