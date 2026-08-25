#!/usr/bin/env python3
# Copyright 2026 Tank Robot Team
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
"""Comprehensive telemetry recorder for offline training data collection.

Records all relevant robot telemetry including:
- Command velocities (cmd_vel)
- Motor commands and encoder feedback
- IMU data (accelerometer, gyroscope)
- Battery state
- Camera images (if available)
- Odometry
- Safety events (e-stop, timeouts)
- Agent commands and proposals
"""

import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSDurabilityPolicy, QoSReliabilityPolicy
from geometry_msgs.msg import Twist
from sensor_msgs.msg import BatteryState, Imu, Image, JointState
from nav_msgs.msg import Odometry
from std_msgs.msg import Bool, Int32MultiArray, String
from diagnostic_msgs.msg import DiagnosticArray

try:
    from rosbag2_py import (
        StorageOptions,
        ConverterOptions,
        SequentialWriter,
    )
    ROSBAG2_AVAILABLE = True
except ImportError:
    ROSBAG2_AVAILABLE = False


class TelemetryRecorder(Node):
    """Comprehensive telemetry recorder with rosbag2 backend."""

    def __init__(self) -> None:
        super().__init__("telemetry_recorder")

        if not ROSBAG2_AVAILABLE:
            self.get_logger().error("rosbag2_py not available. Cannot record telemetry.")
            raise RuntimeError("rosbag2_py required for telemetry recording")

        # Parameters
        self.declare_parameter("bag_dir", "/tmp/tank_robot_telemetry")
        self.declare_parameter("bag_prefix", "telemetry")
        self.declare_parameter("max_bag_size_mb", 1024)
        self.declare_parameter("split_bag", True)
        self.declare_parameter("record_camera", True)
        self.declare_parameter("record_diagnostics", True)
        self.declare_parameter("record_agent", True)
        self.declare_parameter("compression", "zstd")

        self._bag_dir = Path(self.get_parameter("bag_dir").value)
        self._bag_prefix = self.get_parameter("bag_prefix").value
        self._max_bag_size_mb = self.get_parameter("max_bag_size_mb").value
        self._split_bag = self.get_parameter("split_bag").value
        self._record_camera = self.get_parameter("record_camera").value
        self._record_diagnostics = self.get_parameter("record_diagnostics").value
        self._record_agent = self.get_parameter("record_agent").value
        self._compression = self.get_parameter("compression").value

        # Create bag directory
        self._bag_dir.mkdir(parents=True, exist_ok=True)

        # Recording state
        self._recording = False
        self._writer: Optional[SequentialWriter] = None
        self._current_bag_path: Optional[Path] = None
        self._bag_counter = 0
        self._message_count = 0
        self._start_time: Optional[float] = None

        # Telemetry statistics
        self._stats: Dict[str, int] = {
            "cmd_vel": 0,
            "encoder": 0,
            "imu": 0,
            "battery": 0,
            "odometry": 0,
            "camera": 0,
            "diagnostics": 0,
            "safety_events": 0,
            "agent_commands": 0,
        }

        # Setup subscribers
        self._setup_subscribers()

        # Services for recording control
        from std_srvs.srv import SetBool
        self._start_recording_srv = self.create_service(
            SetBool, "/telemetry/start_recording", self._start_recording_callback
        )
        self._stop_recording_srv = self.create_service(
            SetBool, "/telemetry/stop_recording", self._stop_recording_callback
        )

        self.get_logger().info("Telemetry recorder initialized")

    def _setup_subscribers(self) -> None:
        """Setup all telemetry subscribers."""
        # Reliable QoS for critical telemetry
        reliable_qos = QoSProfile(
            depth=10,
            reliability=QoSReliabilityPolicy.RELIABLE,
            durability=QoSDurabilityPolicy.VOLATILE,
        )

        # Best-effort QoS for high-rate data (camera, IMU)
        best_effort_qos = QoSProfile(
            depth=10,
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            durability=QoSDurabilityPolicy.VOLATILE,
        )

        # Command velocities
        self.create_subscription(
            Twist, "/cmd_vel", self._cmd_vel_callback, reliable_qos
        )
        self.create_subscription(
            Twist, "/ranger/cmd_vel_safe", self._safe_cmd_vel_callback, reliable_qos
        )

        # Motor telemetry
        self.create_subscription(
            Int32MultiArray, "/stm32/encoder_ticks", self._encoder_callback, reliable_qos
        )
        self.create_subscription(
            JointState, "/stm32/joint_states", self._joint_state_callback, reliable_qos
        )

        # IMU
        self.create_subscription(
            Imu, "/stm32/imu", self._imu_callback, best_effort_qos
        )

        # Battery
        self.create_subscription(
            BatteryState, "/stm32/battery", self._battery_callback, reliable_qos
        )

        # Odometry
        self.create_subscription(
            Odometry, "/stm32/odom", self._odometry_callback, reliable_qos
        )

        # Camera (optional)
        if self._record_camera:
            self.create_subscription(
                Image, "/camera/image_raw", self._camera_callback, best_effort_qos
            )

        # Diagnostics (optional)
        if self._record_diagnostics:
            self.create_subscription(
                DiagnosticArray,
                "/stm32/diagnostics",
                self._diagnostics_callback,
                reliable_qos,
            )

        # Safety events
        self.create_subscription(
            Bool, "/safety/e_stop", self._estop_callback, reliable_qos
        )
        self.create_subscription(
            Bool, "/stm32/bridge_alive", self._bridge_alive_callback, reliable_qos
        )

        # Agent data (optional)
        if self._record_agent:
            self.create_subscription(
                Twist, "/agent/cmd_vel_proposed", self._agent_cmd_callback, reliable_qos
            )
            self.create_subscription(
                String, "/agent/proposals", self._agent_proposals_callback, reliable_qos
            )

    def _start_recording(self) -> bool:
        """Start a new rosbag recording."""
        if self._recording:
            self.get_logger().warn("Already recording")
            return False

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        bag_name = f"{self._bag_prefix}_{timestamp}_{self._bag_counter:03d}"
        self._current_bag_path = self._bag_dir / bag_name

        storage_options = StorageOptions(
            uri=str(self._current_bag_path),
            max_bag_size=self._max_bag_size_mb * 1024 * 1024 if self._split_bag else 0,
        )

        converter_options = ConverterOptions("", "")

        try:
            self._writer = SequentialWriter()
            self._writer.open(storage_options, converter_options)

            # Create topics
            self._create_topics()

            self._recording = True
            self._start_time = time.monotonic()
            self._message_count = 0
            self._bag_counter += 1

            self.get_logger().info(f"Started recording to {self._current_bag_path}")
            return True

        except Exception as e:
            self.get_logger().error(f"Failed to start recording: {e}")
            return False

    def _stop_recording(self) -> bool:
        """Stop current rosbag recording."""
        if not self._recording:
            self.get_logger().warn("Not recording")
            return False

        try:
            if self._writer:
                self._writer.close()

            duration = time.monotonic() - self._start_time if self._start_time else 0
            rate = self._message_count / duration if duration > 0 else 0

            self.get_logger().info(
                f"Stopped recording: {self._message_count} messages in {duration:.1f}s "
                f"({rate:.1f} msg/s)"
            )
            self.get_logger().info(f"Bag saved to {self._current_bag_path}")
            self.get_logger().info(f"Stats: {self._stats}")

            self._recording = False
            self._writer = None
            return True

        except Exception as e:
            self.get_logger().error(f"Failed to stop recording: {e}")
            return False

    def _create_topics(self) -> None:
        """Create all topics in the rosbag."""
        if not self._writer:
            return

        topics = [
            ("/cmd_vel", "geometry_msgs/msg/Twist"),
            ("/ranger/cmd_vel_safe", "geometry_msgs/msg/Twist"),
            ("/stm32/encoder_ticks", "std_msgs/msg/Int32MultiArray"),
            ("/stm32/joint_states", "sensor_msgs/msg/JointState"),
            ("/stm32/imu", "sensor_msgs/msg/Imu"),
            ("/stm32/battery", "sensor_msgs/msg/BatteryState"),
            ("/stm32/odom", "nav_msgs/msg/Odometry"),
            ("/safety/e_stop", "std_msgs/msg/Bool"),
            ("/stm32/bridge_alive", "std_msgs/msg/Bool"),
        ]

        if self._record_camera:
            topics.append(("/camera/image_raw", "sensor_msgs/msg/Image"))

        if self._record_diagnostics:
            topics.append(("/stm32/diagnostics", "diagnostic_msgs/msg/DiagnosticArray"))

        if self._record_agent:
            topics.extend([
                ("/agent/cmd_vel_proposed", "geometry_msgs/msg/Twist"),
                ("/agent/proposals", "std_msgs/msg/String"),
            ])

        for topic_name, type_name in topics:
            self._writer.create_topic(
                topic_name,
                type_name,
                "",
                "",
            )

    def _write_message(self, topic_name: str, message) -> None:
        """Write a message to the rosbag."""
        if not self._recording or not self._writer:
            return

        try:
            from rclpy.serialization import serialize_message
            self._writer.write(topic_name, serialize_message(
                message), self.get_clock().now().nanoseconds)
            self._message_count += 1
        except Exception as e:
            self.get_logger().error(f"Failed to write message to {topic_name}: {e}")

    # Callbacks
    def _cmd_vel_callback(self, msg: Twist) -> None:
        self._stats["cmd_vel"] += 1
        self._write_message("/cmd_vel", msg)

    def _safe_cmd_vel_callback(self, msg: Twist) -> None:
        self._write_message("/ranger/cmd_vel_safe", msg)

    def _encoder_callback(self, msg: Int32MultiArray) -> None:
        self._stats["encoder"] += 1
        self._write_message("/stm32/encoder_ticks", msg)

    def _joint_state_callback(self, msg: JointState) -> None:
        self._write_message("/stm32/joint_states", msg)

    def _imu_callback(self, msg: Imu) -> None:
        self._stats["imu"] += 1
        self._write_message("/stm32/imu", msg)

    def _battery_callback(self, msg: BatteryState) -> None:
        self._stats["battery"] += 1
        self._write_message("/stm32/battery", msg)

    def _odometry_callback(self, msg: Odometry) -> None:
        self._stats["odometry"] += 1
        self._write_message("/stm32/odom", msg)

    def _camera_callback(self, msg: Image) -> None:
        self._stats["camera"] += 1
        self._write_message("/camera/image_raw", msg)

    def _diagnostics_callback(self, msg: DiagnosticArray) -> None:
        self._stats["diagnostics"] += 1
        self._write_message("/stm32/diagnostics", msg)

    def _estop_callback(self, msg: Bool) -> None:
        if msg.data:
            self._stats["safety_events"] += 1
        self._write_message("/safety/e_stop", msg)

    def _bridge_alive_callback(self, msg: Bool) -> None:
        self._write_message("/stm32/bridge_alive", msg)

    def _agent_cmd_callback(self, msg: Twist) -> None:
        self._stats["agent_commands"] += 1
        self._write_message("/agent/cmd_vel_proposed", msg)

    def _agent_proposals_callback(self, msg: String) -> None:
        self._write_message("/agent/proposals", msg)

    # Service callbacks
    def _start_recording_callback(self, request, response) -> None:
        """Service callback to start recording."""
        success = self._start_recording()
        response.success = success
        response.message = "Recording started" if success else "Failed to start recording"
        return response

    def _stop_recording_callback(self, request, response) -> None:
        """Service callback to stop recording."""
        success = self._stop_recording()
        response.success = success
        response.message = "Recording stopped" if success else "Failed to stop recording"
        return response


def main(args=None) -> None:
    rclpy.init(args=args)
    node = TelemetryRecorder()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node._recording:
            node._stop_recording()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
