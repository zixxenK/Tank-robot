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
"""Rosbag2 parser for extracting training data from recorded telemetry."""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

try:
    from rosbag2_py import StorageOptions, SequentialReader
    ROSBAG2_AVAILABLE = True
except ImportError:
    ROSBAG2_AVAILABLE = False


@dataclass
class TelemetrySample:
    """Single telemetry sample for training."""
    timestamp: float
    cmd_vel_linear: float
    cmd_vel_angular: float
    encoder_left: int
    encoder_right: int
    imu_accel_x: float
    imu_accel_y: float
    imu_accel_z: float
    imu_gyro_x: float
    imu_gyro_y: float
    imu_gyro_z: float
    battery_voltage: float
    battery_current: float
    odometry_x: float
    odometry_y: float
    odometry_yaw: float
    linear_velocity_x: float
    angular_velocity_z: float
    estop_active: bool
    bridge_alive: bool


class BagParser:
    """Parse rosbag2 files and extract structured telemetry data."""

    def __init__(self, bag_path: str) -> None:
        if not ROSBAG2_AVAILABLE:
            raise RuntimeError("rosbag2_py required for bag parsing")

        self._bag_path = Path(bag_path)
        if not self._bag_path.exists():
            raise FileNotFoundError(f"Bag not found: {bag_path}")

        self._reader: Optional[SequentialReader] = None
        self._storage_options = StorageOptions(uri=str(self._bag_path))

    def open(self) -> None:
        """Open the rosbag for reading."""
        self._reader = SequentialReader()
        self._reader.open(self._storage_options)

    def close(self) -> None:
        """Close the rosbag."""
        if self._reader:
            self._reader = None

    def get_topics(self) -> Dict[str, str]:
        """Get all topics and their types."""
        if not self._reader:
            raise RuntimeError("Bag not open")

        return self._reader.get_all_topics_and_types()

    def extract_samples(self, max_samples: Optional[int] = None) -> List[TelemetrySample]:
        """Extract telemetry samples from the bag."""
        if not self._reader:
            raise RuntimeError("Bag not open")

        samples: List[TelemetrySample] = []

        # Temporary storage for latest values from each topic
        state: Dict[str, Any] = {
            "cmd_vel_linear": 0.0,
            "cmd_vel_angular": 0.0,
            "encoder_left": 0,
            "encoder_right": 0,
            "imu_accel": (0.0, 0.0, 0.0),
            "imu_gyro": (0.0, 0.0, 0.0),
            "battery_voltage": 0.0,
            "battery_current": 0.0,
            "odometry": (0.0, 0.0, 0.0),
            "odometry_twist": (0.0, 0.0),
            "estop_active": False,
            "bridge_alive": False,
        }

        while self._reader.has_next():
            (topic, data, timestamp) = self._reader.read_next()

            # Parse message based on topic
            if topic == "/cmd_vel":
                from geometry_msgs.msg import Twist
                from rclpy.serialization import deserialize_message
                msg = deserialize_message(data, Twist)
                state["cmd_vel_linear"] = msg.linear.x
                state["cmd_vel_angular"] = msg.angular.z

            elif topic == "/stm32/encoder_ticks":
                from std_msgs.msg import Int32MultiArray
                from rclpy.serialization import deserialize_message
                msg = deserialize_message(data, Int32MultiArray)
                if len(msg.data) >= 2:
                    state["encoder_left"] = msg.data[0]
                    state["encoder_right"] = msg.data[1]

            elif topic == "/stm32/imu":
                from sensor_msgs.msg import Imu
                from rclpy.serialization import deserialize_message
                msg = deserialize_message(data, Imu)
                state["imu_accel"] = (msg.linear_acceleration.x,
                                      msg.linear_acceleration.y,
                                      msg.linear_acceleration.z)
                state["imu_gyro"] = (msg.angular_velocity.x,
                                     msg.angular_velocity.y,
                                     msg.angular_velocity.z)

            elif topic == "/stm32/battery":
                from sensor_msgs.msg import BatteryState
                from rclpy.serialization import deserialize_message
                msg = deserialize_message(data, BatteryState)
                state["battery_voltage"] = msg.voltage
                state["battery_current"] = msg.current if hasattr(msg, 'current') else 0.0

            elif topic == "/stm32/odom":
                from nav_msgs.msg import Odometry
                from rclpy.serialization import deserialize_message
                msg = deserialize_message(data, Odometry)
                state["odometry"] = (msg.pose.pose.position.x,
                                     msg.pose.pose.position.y,
                                     0.0)  # Simplified yaw
                state["odometry_twist"] = (msg.twist.twist.linear.x,
                                           msg.twist.twist.angular.z)

            elif topic == "/safety/e_stop":
                from std_msgs.msg import Bool
                from rclpy.serialization import deserialize_message
                msg = deserialize_message(data, Bool)
                state["estop_active"] = msg.data

            elif topic == "/stm32/bridge_alive":
                from std_msgs.msg import Bool
                from rclpy.serialization import deserialize_message
                msg = deserialize_message(data, Bool)
                state["bridge_alive"] = msg.data

            # Create sample when we have encoder data (indicates active control)
            if topic == "/stm32/encoder_ticks":
                sample = TelemetrySample(
                    timestamp=timestamp / 1e9,
                    cmd_vel_linear=state["cmd_vel_linear"],
                    cmd_vel_angular=state["cmd_vel_angular"],
                    encoder_left=state["encoder_left"],
                    encoder_right=state["encoder_right"],
                    imu_accel_x=state["imu_accel"][0],
                    imu_accel_y=state["imu_accel"][1],
                    imu_accel_z=state["imu_accel"][2],
                    imu_gyro_x=state["imu_gyro"][0],
                    imu_gyro_y=state["imu_gyro"][1],
                    imu_gyro_z=state["imu_gyro"][2],
                    battery_voltage=state["battery_voltage"],
                    battery_current=state["battery_current"],
                    odometry_x=state["odometry"][0],
                    odometry_y=state["odometry"][1],
                    odometry_yaw=state["odometry"][2],
                    linear_velocity_x=state["odometry_twist"][0],
                    angular_velocity_z=state["odometry_twist"][1],
                    estop_active=state["estop_active"],
                    bridge_alive=state["bridge_alive"],
                )
                samples.append(sample)

                if max_samples and len(samples) >= max_samples:
                    break

        return samples

    def export_to_json(self, output_path: str, max_samples: Optional[int] = None) -> None:
        """Export telemetry samples to JSON file."""
        samples = self.extract_samples(max_samples)
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        data = [asdict(sample) for sample in samples]
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"Exported {len(samples)} samples to {output_path}")

    def export_to_csv(self, output_path: str, max_samples: Optional[int] = None) -> None:
        """Export telemetry samples to CSV file."""
        import csv

        samples = self.extract_samples(max_samples)
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        if not samples:
            print("No samples to export")
            return

        fieldnames = list(asdict(samples[0]).keys())
        with open(output_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for sample in samples:
                writer.writerow(asdict(sample))

        print(f"Exported {len(samples)} samples to {output_path}")


def main() -> None:
    """CLI for bag parsing."""
    import argparse

    parser = argparse.ArgumentParser(description="Parse rosbag2 files for training data")
    parser.add_argument("bag_path", help="Path to rosbag2 directory")
    parser.add_argument("--output", "-o", default="telemetry_data.json", help="Output file path")
    parser.add_argument("--format", choices=["json", "csv"], default="json", help="Output format")
    parser.add_argument("--max-samples", type=int, help="Maximum number of samples to extract")

    args = parser.parse_args()

    if not ROSBAG2_AVAILABLE:
        print("Error: rosbag2_py not available")
        return

    parser_instance = BagParser(args.bag_path)
    parser_instance.open()

    try:
        if args.format == "json":
            parser_instance.export_to_json(args.output, args.max_samples)
        else:
            parser_instance.export_to_csv(args.output, args.max_samples)
    finally:
        parser_instance.close()


if __name__ == "__main__":
    main()
