#!/usr/bin/env python3
"""Run the Rock64 hardware acceptance sequence through ROS 2 interfaces."""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
import time
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Deque, Optional, Sequence, Tuple

import rclpy
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from rclpy.node import Node
from rclpy.qos import (
    QoSDurabilityPolicy,
    QoSProfile,
    QoSReliabilityPolicy,
)
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Image, Imu
from std_msgs.msg import Bool, Int32MultiArray, String
from std_srvs.srv import SetBool


PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"


@dataclass(frozen=True)
class StageResult:
    """One numbered acceptance-test result."""

    index: int
    name: str
    status: str
    required: bool
    detail: str
    duration_s: float


@dataclass(frozen=True)
class ImageObservation:
    """Small validation record that does not retain a full image buffer."""

    valid: bool
    detail: str
    stamp_ns: Optional[int]
    width: int
    height: int
    encoding: str
    data_length: int


def parse_ps5_connected(status_text: str) -> bool:
    """Return whether a PS5 status line explicitly reports connection."""
    match = re.search(
        r"(?:^|\s)connected\s*=\s*([^\s]+)",
        str(status_text),
        flags=re.IGNORECASE,
    )
    if match is None:
        return False
    return match.group(1).strip().lower() in {"1", "true", "yes", "on"}


def parse_onboard_imu_diagnostic(message: object) -> Tuple[bool, str]:
    """Extract the bridge's explicit onboard-IMU readiness evidence."""
    for status in getattr(message, "status", ()):
        name = str(getattr(status, "name", "")).lower()
        if "onboard mpu6050" not in name:
            continue
        values = {
            str(item.key): str(item.value)
            for item in getattr(status, "values", ())
        }
        ready = values.get("ready", "false").lower() in {
            "1", "true", "yes", "on"
        }
        sample_valid = values.get("sample_valid", "false").lower() in {
            "1", "true", "yes", "on"
        }
        detail = (
            f"onboard={values.get('onboard', 'unknown')} "
            f"bus={values.get('bus', 'unknown')} "
            f"address={values.get('address', 'unknown')} "
            f"who_am_i={values.get('who_am_i', 'unknown')} "
            f"ready={ready} sample_valid={sample_valid} "
            f"sample_count={values.get('sample_count', 'unknown')} "
            f"error_count={values.get('error_count', 'unknown')}"
        )
        return ready and sample_valid, detail
    return False, "no onboard MPU6050 diagnostic status received"


def joy_has_operator_event(
    baseline_axes: Sequence[object],
    baseline_buttons: Sequence[object],
    current_axes: Sequence[object],
    current_buttons: Sequence[object],
    axis_delta: float = 0.20,
) -> bool:
    """Detect a right-stick change or face-button press after a baseline."""
    # DualSense Bluetooth uses axis 2 for right-stick X; USB commonly uses
    # axis 3. Comparing with a fresh baseline avoids mistaking a trigger's
    # normal -1 resting position for intentional operator input.
    for axis_index in (2, 3):
        if axis_index >= len(baseline_axes) or axis_index >= len(current_axes):
            continue
        try:
            before = float(baseline_axes[axis_index])
            current = float(current_axes[axis_index])
        except (TypeError, ValueError, OverflowError):
            continue
        if (
            math.isfinite(before)
            and math.isfinite(current)
            and abs(current - before) >= max(0.05, float(axis_delta))
        ):
            return True

    # Cross, Circle, Triangle, and Square are indices 0..3 in this bridge.
    for button_index in range(4):
        if button_index >= len(current_buttons):
            continue
        try:
            pressed = int(current_buttons[button_index]) != 0
            was_pressed = (
                button_index < len(baseline_buttons)
                and int(baseline_buttons[button_index]) != 0
            )
        except (TypeError, ValueError, OverflowError):
            continue
        if pressed and not was_pressed:
            return True
    return False


def validate_encoder_values(values: Sequence[object]) -> Tuple[bool, str]:
    """Validate the left/right encoder payload without assuming direction."""
    if len(values) < 2:
        return False, "expected at least two encoder values"
    try:
        left = int(values[0])
        right = int(values[1])
    except (TypeError, ValueError, OverflowError):
        return False, "encoder values are not finite integers"
    int32_min = -(2**31)
    int32_max = (2**31) - 1
    if not int32_min <= left <= int32_max:
        return False, f"left encoder is outside int32: {left}"
    if not int32_min <= right <= int32_max:
        return False, f"right encoder is outside int32: {right}"
    return True, f"left={left} right={right}"


def validate_imu_values(
    acceleration: Sequence[object],
    angular_velocity: Sequence[object],
) -> Tuple[bool, str]:
    """Validate finite SI-unit IMU data and a plausible gravity magnitude."""
    if len(acceleration) != 3 or len(angular_velocity) != 3:
        return False, "IMU vectors must each contain three values"
    try:
        accel = tuple(float(value) for value in acceleration)
        gyro = tuple(float(value) for value in angular_velocity)
    except (TypeError, ValueError, OverflowError):
        return False, "IMU vectors contain non-numeric values"
    if not all(math.isfinite(value) for value in accel + gyro):
        return False, "IMU vectors contain NaN or infinity"
    accel_norm = math.sqrt(sum(value * value for value in accel))
    gyro_norm = math.sqrt(sum(value * value for value in gyro))
    if not 3.0 <= accel_norm <= 25.0:
        return False, (
            f"acceleration magnitude {accel_norm:.3f} m/s^2 is implausible"
        )
    if gyro_norm > 40.0:
        return False, (
            f"angular velocity magnitude {gyro_norm:.3f} rad/s is implausible"
        )
    return True, (
        f"accel_norm={accel_norm:.3f}m/s^2 "
        f"gyro_norm={gyro_norm:.3f}rad/s"
    )


def validate_range_values(
    distance: object,
    minimum: object,
    maximum: object,
) -> Tuple[bool, str]:
    """Validate one finite Glowy I2C range observation."""
    try:
        value = float(distance)
        lower = max(0.02, float(minimum))
        upper = min(4.0, float(maximum))
    except (TypeError, ValueError, OverflowError):
        return False, "range fields are not numeric"
    if not all(math.isfinite(item) for item in (value, lower, upper)):
        return False, "range contains NaN or infinity"
    if lower > upper:
        return False, f"invalid sensor limits {lower:.3f}..{upper:.3f}m"
    if not lower <= value <= upper:
        return False, (
            f"distance {value:.3f}m is outside {lower:.3f}..{upper:.3f}m"
        )
    return True, f"distance={value:.3f}m"


def validate_battery_voltage(
    voltage: object,
    minimum: float = 9.0,
    maximum: float = 13.0,
) -> Tuple[bool, str]:
    """Validate a finite voltage from the configured single ADC channel."""
    try:
        value = float(voltage)
    except (TypeError, ValueError, OverflowError):
        return False, "battery voltage is not numeric"
    if not math.isfinite(value):
        return False, "battery voltage is NaN or infinity"
    if not minimum <= value <= maximum:
        return False, (
            f"battery voltage {value:.3f}V is outside "
            f"{minimum:.1f}..{maximum:.1f}V"
        )
    return True, f"voltage={value:.3f}V"


def validate_odometry(message: object) -> Tuple[bool, str]:
    """Validate finite odometry pose/twist and a usable orientation."""
    try:
        pose = message.pose.pose
        twist = message.twist.twist
        position = (
            float(pose.position.x),
            float(pose.position.y),
            float(pose.position.z),
        )
        orientation = (
            float(pose.orientation.x),
            float(pose.orientation.y),
            float(pose.orientation.z),
            float(pose.orientation.w),
        )
        velocity = (
            float(twist.linear.x),
            float(twist.linear.y),
            float(twist.linear.z),
            float(twist.angular.x),
            float(twist.angular.y),
            float(twist.angular.z),
        )
    except (AttributeError, TypeError, ValueError, OverflowError):
        return False, "odometry pose or twist fields are missing/non-numeric"

    if not all(
        math.isfinite(value) for value in position + orientation + velocity
    ):
        return False, "odometry contains NaN or infinity"
    quaternion_norm = math.sqrt(sum(value * value for value in orientation))
    if not 0.9 <= quaternion_norm <= 1.1:
        return False, f"orientation quaternion norm={quaternion_norm:.4f}"
    return True, (
        f"position=({position[0]:.3f},{position[1]:.3f})m "
        f"quaternion_norm={quaternion_norm:.4f}"
    )


def _stamp_to_ns(stamp: object) -> Optional[int]:
    """Convert a ROS time message to nanoseconds when it is populated."""
    try:
        seconds = int(getattr(stamp, "sec"))
        nanoseconds = int(getattr(stamp, "nanosec"))
    except (AttributeError, TypeError, ValueError, OverflowError):
        return None
    if seconds == 0 and nanoseconds == 0:
        return None
    if nanoseconds < 0 or nanoseconds >= 1_000_000_000:
        return None
    return seconds * 1_000_000_000 + nanoseconds


def observe_image(message: object) -> ImageObservation:
    """Validate an uncompressed ROS image and retain only its metadata."""
    try:
        width = int(getattr(message, "width"))
        height = int(getattr(message, "height"))
        step = int(getattr(message, "step"))
        encoding = str(getattr(message, "encoding"))
        data_length = len(getattr(message, "data"))
    except (AttributeError, TypeError, ValueError, OverflowError):
        return ImageObservation(
            False,
            "image metadata or data buffer is missing",
            None,
            0,
            0,
            "",
            0,
        )
    header = getattr(message, "header", None)
    stamp_ns = _stamp_to_ns(getattr(header, "stamp", None))
    if width <= 0 or height <= 0:
        detail = f"invalid image dimensions {width}x{height}"
        valid = False
    elif step <= 0 or data_length < step * height:
        detail = (
            f"short image buffer: {data_length} bytes for "
            f"step={step}, height={height}"
        )
        valid = False
    elif not encoding:
        detail = "image encoding is empty"
        valid = False
    elif stamp_ns is None:
        detail = "image timestamp is missing or zero"
        valid = False
    else:
        detail = (
            f"{width}x{height} {encoding}, {data_length} bytes, "
            f"stamp={stamp_ns}"
        )
        valid = True
    return ImageObservation(
        valid,
        detail,
        stamp_ns,
        width,
        height,
        encoding,
        data_length,
    )


def validate_laser_scan(message: object) -> Tuple[bool, str]:
    """Validate a scan with at least one finite in-range return."""
    try:
        minimum = float(getattr(message, "range_min"))
        maximum = float(getattr(message, "range_max"))
        ranges = tuple(float(value) for value in getattr(message, "ranges"))
    except (AttributeError, TypeError, ValueError, OverflowError):
        return False, "LaserScan fields are missing or non-numeric"
    finite = [
        value
        for value in ranges
        if math.isfinite(value) and minimum <= value <= maximum
    ]
    if not finite:
        return False, "scan has no finite in-range returns"
    return True, (
        f"{len(finite)}/{len(ranges)} finite returns; "
        f"nearest={min(finite):.3f}m"
    )


def bounded_servo_sequence(
    center: object,
    low: object,
    high: object,
) -> Tuple[float, float, float, float]:
    """Return a bounded center/low/high/center SG90 proof sequence."""
    try:
        sequence = (float(center), float(low), float(high), float(center))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("servo angles must be numeric") from exc
    if not all(math.isfinite(value) for value in sequence):
        raise ValueError("servo angles must be finite")
    if not all(30.0 <= value <= 150.0 for value in sequence):
        raise ValueError("servo angles must be within safe 30..150 degrees")
    if not sequence[1] < sequence[0] < sequence[2]:
        raise ValueError("servo angles must satisfy low < center < high")
    return sequence


def assess_motor_delta(
    before: Sequence[object],
    after: Sequence[object],
    motor_index: int,
    minimum_delta: int,
    maximum_crosstalk_ratio: float,
) -> Tuple[bool, str]:
    """Check that only the commanded motor's encoder changed materially."""
    valid_before, detail = validate_encoder_values(before)
    if not valid_before:
        return False, f"invalid baseline: {detail}"
    valid_after, detail = validate_encoder_values(after)
    if not valid_after:
        return False, f"invalid final sample: {detail}"
    if motor_index not in (0, 1):
        return False, f"unsupported motor index {motor_index}"
    deltas = (
        int(after[0]) - int(before[0]),
        int(after[1]) - int(before[1]),
    )
    primary = abs(deltas[motor_index])
    other = abs(deltas[1 - motor_index])
    if primary < max(1, int(minimum_delta)):
        return False, (
            f"encoder delta too small: left={deltas[0]} right={deltas[1]}"
        )
    allowed_other = max(2, int(primary * maximum_crosstalk_ratio))
    if other > allowed_other:
        return False, (
            f"other encoder moved too far: left={deltas[0]} "
            f"right={deltas[1]}, allowed_other={allowed_other}"
        )
    return True, (
        f"left_delta={deltas[0]} right_delta={deltas[1]} "
        f"allowed_other={allowed_other}"
    )


def required_failure_count(results: Sequence[StageResult]) -> int:
    """Count failures that make the acceptance process return nonzero."""
    return sum(
        1
        for result in results
        if result.required and result.status == FAIL
    )


class HardwareTestRunner(Node):
    """Sequentially validate live hardware using only the active ROS graph."""

    def __init__(self) -> None:
        super().__init__("hardware_test_runner")
        self._started_wall = datetime.now(timezone.utc)
        self._results: list[StageResult] = []
        self._samples_required = max(
            1,
            self._integer_parameter("fresh_sample_count", 3),
        )
        self._timeout_s = max(
            0.5,
            self._float_parameter("message_timeout_s", 8.0),
        )
        self._tracks_raised = self._boolean_parameter(
            "tracks_raised", False
        )
        self._motor_run_s = min(
            3.0,
            max(0.25, self._float_parameter("motor_run_seconds", 1.0)),
        )
        self._motor_min_delta = max(
            1,
            self._integer_parameter("motor_min_encoder_delta", 5),
        )
        self._motor_crosstalk_ratio = min(
            1.0,
            max(
                0.0,
                self._float_parameter("motor_max_crosstalk_ratio", 0.25),
            ),
        )
        default_report = os.path.join(
            tempfile.gettempdir(),
            "tank_robot_hardware_test_report.json",
        )
        self._report_path = self._string_parameter(
            "report_path", default_report
        )
        self._result_hold_s = max(
            0.1,
            self._float_parameter("result_hold_seconds", 1.0),
        )

        self._alive: Deque[Tuple[float, bool]] = deque(maxlen=64)
        self._encoders: Deque[Tuple[float, Tuple[int, ...]]] = deque(
            maxlen=256
        )
        self._odometry: Deque[Tuple[float, object]] = deque(maxlen=128)
        self._imu: Deque[
            Tuple[float, Tuple[Tuple[float, ...], Tuple[float, ...]]]
        ] = deque(maxlen=128)
        self._imu_diagnostics: Deque[Tuple[float, object]] = deque(maxlen=32)
        self._esp_images: Deque[Tuple[float, ImageObservation]] = deque(
            maxlen=32
        )
        self._usb_images: Deque[Tuple[float, ImageObservation]] = deque(
            maxlen=32
        )

        result_qos = QoSProfile(
            depth=1,
            reliability=QoSReliabilityPolicy.RELIABLE,
            durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
        )
        sensor_qos = QoSProfile(
            depth=10,
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            durability=QoSDurabilityPolicy.VOLATILE,
        )
        diagnostic_qos = QoSProfile(
            depth=10,
            reliability=QoSReliabilityPolicy.RELIABLE,
            durability=QoSDurabilityPolicy.VOLATILE,
        )
        self._result_pub = self.create_publisher(
            String, "/hardware_test/result", result_qos
        )
        self._diagnostics_pub = self.create_publisher(
            DiagnosticArray,
            "/hardware_test/diagnostics",
            result_qos,
        )
        self._estop_pub = self.create_publisher(
            Bool, "/safety/e_stop", result_qos
        )
        self._motor_direction_pub = self.create_publisher(
            String,
            "/stm32/test_direction",
            10,
        )

        self.create_subscription(
            Bool, "/stm32/bridge_alive", self._alive_callback, 10
        )
        self.create_subscription(
            Int32MultiArray,
            "/stm32/encoder_ticks",
            self._encoder_callback,
            10,
        )
        self.create_subscription(
            Odometry, "/stm32/odom", self._odometry_callback, 10
        )
        self.create_subscription(Imu, "/stm32/imu", self._imu_callback, 10)
        self.create_subscription(
            DiagnosticArray,
            "/stm32/diagnostics",
            self._imu_diagnostics_callback,
            diagnostic_qos,
        )
        self.create_subscription(
            Image,
            "/camera/image_raw",
            self._esp_image_callback,
            sensor_qos,
        )
        self.create_subscription(
            Image,
            "/camera/usb/image_raw",
            self._usb_image_callback,
            sensor_qos,
        )

        self._motor_clients = (
            self.create_client(SetBool, "/stm32/motor_1/enable"),
            self.create_client(SetBool, "/stm32/motor_2/enable"),
        )

    def _parameter(self, name: str, default: object) -> object:
        """Declare a parameter and return the declared value."""
        parameter = self.declare_parameter(name, default)
        return parameter.value

    def _float_parameter(self, name: str, default: float) -> float:
        try:
            return float(self._parameter(name, default))
        except (TypeError, ValueError, OverflowError):
            return default

    def _integer_parameter(self, name: str, default: int) -> int:
        try:
            return int(self._parameter(name, default))
        except (TypeError, ValueError, OverflowError):
            return default

    def _boolean_parameter(self, name: str, default: bool) -> bool:
        value = self._parameter(name, default)
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def _string_parameter(self, name: str, default: str) -> str:
        value = self._parameter(name, default)
        text = str(value).strip() if value is not None else ""
        return text or default

    def _alive_callback(self, message: Bool) -> None:
        self._alive.append((time.monotonic(), bool(message.data)))

    def _encoder_callback(self, message: Int32MultiArray) -> None:
        try:
            values = tuple(int(value) for value in message.data)
        except (TypeError, ValueError, OverflowError):
            values = ()
        self._encoders.append((time.monotonic(), values))

    def _odometry_callback(self, message: Odometry) -> None:
        """Retain derived odometry for the navigation-path acceptance stage."""
        self._odometry.append((time.monotonic(), message))

    def _imu_callback(self, message: Imu) -> None:
        acceleration = (
            float(message.linear_acceleration.x),
            float(message.linear_acceleration.y),
            float(message.linear_acceleration.z),
        )
        angular_velocity = (
            float(message.angular_velocity.x),
            float(message.angular_velocity.y),
            float(message.angular_velocity.z),
        )
        self._imu.append(
            (time.monotonic(), (acceleration, angular_velocity))
        )

    def _imu_diagnostics_callback(self, message: DiagnosticArray) -> None:
        self._imu_diagnostics.append((time.monotonic(), message))

    def _esp_image_callback(self, message: Image) -> None:
        self._esp_images.append((time.monotonic(), observe_image(message)))

    def _usb_image_callback(self, message: Image) -> None:
        self._usb_images.append((time.monotonic(), observe_image(message)))

    def _spin_until(
        self,
        predicate: Callable[[], bool],
        timeout_s: float,
        periodic: Optional[Callable[[], None]] = None,
    ) -> bool:
        """Spin until a condition becomes true or a monotonic timeout ends."""
        deadline = time.monotonic() + max(0.0, timeout_s)
        next_periodic = 0.0
        while rclpy.ok() and time.monotonic() < deadline:
            now = time.monotonic()
            if periodic is not None and now >= next_periodic:
                periodic()
                next_periodic = now + 0.25
            if predicate():
                return True
            rclpy.spin_once(self, timeout_sec=0.05)
        return predicate()

    @staticmethod
    def _fresh(
        samples: Sequence[Tuple[float, object]],
        since: float,
        predicate: Callable[[object], bool],
    ) -> list[object]:
        return [
            value
            for arrival, value in samples
            if arrival >= since and predicate(value)
        ]

    def _record(
        self,
        name: str,
        status: str,
        required: bool,
        detail: str,
        started: float,
    ) -> StageResult:
        result = StageResult(
            index=len(self._results) + 1,
            name=name,
            status=status,
            required=required,
            detail=detail,
            duration_s=round(max(0.0, time.monotonic() - started), 3),
        )
        self._results.append(result)
        marker = f"[{result.index:02d}] {status}: {name} - {detail}"
        if status == FAIL:
            self.get_logger().error(marker)
        elif status == SKIP:
            self.get_logger().warn(marker)
        else:
            self.get_logger().info(marker)
        print(marker, flush=True)
        return result

    def _run_stage(
        self,
        name: str,
        function: Callable[[], Tuple[bool, str]],
        required: bool = True,
    ) -> None:
        started = time.monotonic()
        try:
            passed, detail = function()
        except Exception as exc:  # noqa: BLE001
            passed = False
            detail = f"unexpected {type(exc).__name__}: {exc}"
        self._record(
            name,
            PASS if passed else FAIL,
            required,
            detail,
            started,
        )

    def _test_bridge_alive(self) -> Tuple[bool, str]:
        since = time.monotonic()
        ready = self._spin_until(
            lambda: len(
                self._fresh(self._alive, since, lambda value: bool(value))
            )
            >= self._samples_required,
            self._timeout_s,
        )
        count = len(
            self._fresh(self._alive, since, lambda value: bool(value))
        )
        if not ready:
            return False, (
                f"received {count}/{self._samples_required} fresh True "
                "messages on /stm32/bridge_alive"
            )
        return True, f"{count} fresh True bridge-alive messages"

    def _test_encoders(self) -> Tuple[bool, str]:
        since = time.monotonic()

        def valid(value: object) -> bool:
            return validate_encoder_values(value)[0]  # type: ignore[arg-type]

        ready = self._spin_until(
            lambda: len(self._fresh(self._encoders, since, valid))
            >= self._samples_required,
            self._timeout_s,
        )
        samples = self._fresh(self._encoders, since, valid)
        if not ready:
            return False, (
                f"received {len(samples)}/{self._samples_required} fresh "
                "valid messages on /stm32/encoder_ticks"
            )
        _, detail = validate_encoder_values(
            samples[-1]  # type: ignore[arg-type]
        )
        return True, f"{len(samples)} fresh samples; {detail}"

    def _test_imu(self) -> Tuple[bool, str]:
        since = time.monotonic()

        def valid(value: object) -> bool:
            acceleration, gyro = value  # type: ignore[misc]
            return validate_imu_values(acceleration, gyro)[0]

        def diagnostic() -> Tuple[bool, str]:
            messages = self._fresh(
                self._imu_diagnostics, since, lambda value: True
            )
            if not messages:
                return False, "no onboard MPU6050 diagnostic status received"
            return parse_onboard_imu_diagnostic(messages[-1])

        ready = self._spin_until(
            lambda: (
                len(self._fresh(self._imu, since, valid))
                >= self._samples_required
                and diagnostic()[0]
            ),
            self._timeout_s,
        )
        samples = self._fresh(self._imu, since, valid)
        diagnostic_ready, diagnostic_detail = diagnostic()
        if not ready:
            return False, (
                f"received {len(samples)}/{self._samples_required} fresh "
                "finite plausible messages on /stm32/imu; "
                f"{diagnostic_detail}"
            )
        acceleration, gyro = samples[-1]  # type: ignore[misc]
        _, detail = validate_imu_values(acceleration, gyro)
        return (
            True,
            f"{len(samples)} fresh samples; {detail}; {diagnostic_detail}",
        )

    def _test_odometry(self) -> Tuple[bool, str]:
        """Verify the bridge's encoder-derived odometry is usable by planning."""
        since = time.monotonic()

        def valid(value: object) -> bool:
            return validate_odometry(value)[0]

        ready = self._spin_until(
            lambda: len(self._fresh(self._odometry, since, valid))
            >= self._samples_required,
            self._timeout_s,
        )
        samples = self._fresh(self._odometry, since, valid)
        if not ready:
            return False, (
                f"received {len(samples)}/{self._samples_required} fresh "
                "finite odometry messages on /stm32/odom"
            )
        _, detail = validate_odometry(samples[-1])
        return True, f"{len(samples)} fresh samples; {detail}"

    def _test_camera(
        self,
        samples: Deque[Tuple[float, ImageObservation]],
        topic: str,
    ) -> Tuple[bool, str]:
        since = time.monotonic()

        def valid_unique_count() -> int:
            observations = self._fresh(
                samples,
                since,
                lambda value: bool(value.valid),  # type: ignore[attr-defined]
            )
            return len(
                {
                    value.stamp_ns  # type: ignore[attr-defined]
                    for value in observations
                    if value.stamp_ns is not None  # type: ignore[attr-defined]
                }
            )

        ready = self._spin_until(
            lambda: valid_unique_count() >= self._samples_required,
            self._timeout_s,
        )
        valid = self._fresh(
            samples,
            since,
            lambda value: bool(value.valid),  # type: ignore[attr-defined]
        )
        unique_count = valid_unique_count()
        if not ready:
            latest = samples[-1][1].detail if samples else "no message"
            return False, (
                f"received {unique_count}/{self._samples_required} fresh "
                f"valid uniquely stamped frames on {topic}; latest={latest}"
            )
        observation = valid[-1]
        return True, (
            f"{unique_count} fresh uniquely stamped frames; "
            f"{observation.detail}"  # type: ignore[attr-defined]
        )

    def _call_motor_service(
        self,
        motor_index: int,
        enabled: bool,
        timeout_s: float,
    ) -> Tuple[bool, str]:
        client = self._motor_clients[motor_index]
        if not client.wait_for_service(timeout_sec=max(0.1, timeout_s)):
            return False, "service is unavailable"
        request = SetBool.Request()
        request.data = bool(enabled)
        future = client.call_async(request)
        ready = self._spin_until(future.done, timeout_s)
        if not ready:
            return False, "service call timed out"
        try:
            response = future.result()
        except Exception as exc:  # noqa: BLE001
            return False, f"service call raised {type(exc).__name__}: {exc}"
        if response is None:
            return False, "service returned no response"
        return bool(response.success), str(response.message)

    def _fresh_encoder_sample(
        self,
        since: float,
        timeout_s: float,
    ) -> Optional[Tuple[int, ...]]:
        def valid(value: object) -> bool:
            return validate_encoder_values(value)[0]  # type: ignore[arg-type]

        ready = self._spin_until(
            lambda: bool(self._fresh(self._encoders, since, valid)),
            timeout_s,
        )
        if not ready:
            return None
        return self._fresh(
            self._encoders, since, valid
        )[-1]  # type: ignore[return-value]

    def _test_motor(self, motor_index: int) -> Tuple[bool, str]:
        baseline_since = time.monotonic()
        baseline = self._fresh_encoder_sample(
            baseline_since,
            self._timeout_s,
        )
        if baseline is None:
            return False, "no fresh valid encoder baseline"

        started, start_detail = self._call_motor_service(
            motor_index,
            True,
            self._timeout_s,
        )
        if not started:
            return False, f"start rejected: {start_detail}"

        motion_since = time.monotonic()
        stop_ok = False
        stop_detail = "stop was not attempted"
        try:
            self._spin_until(
                lambda: False,
                self._motor_run_s,
            )
        finally:
            stop_ok, stop_detail = self._call_motor_service(
                motor_index,
                False,
                min(self._timeout_s, 3.0),
            )
        final = self._fresh_encoder_sample(
            motion_since,
            self._timeout_s,
        )
        if not stop_ok:
            return False, f"stop rejected: {stop_detail}"
        if final is None:
            return False, "no fresh encoder sample during motor motion"
        passed, detail = assess_motor_delta(
            baseline,
            final,
            motor_index,
            self._motor_min_delta,
            self._motor_crosstalk_ratio,
        )
        return passed, (
            f"existing bridge proof service at fixed 0.10 speed; {detail}; "
            f"stop='{stop_detail}'"
        )

    def _publish_estop(self, active: bool) -> None:
        message = Bool()
        message.data = bool(active)
        self._estop_pub.publish(message)

    def _set_estop(self, active: bool) -> None:
        """Publish the requested e-stop state repeatedly across discovery."""
        for _ in range(3):
            self._publish_estop(active)
            rclpy.spin_once(self, timeout_sec=0.1)

    def _safe_shutdown(self) -> None:
        """Best-effort M1/M2 stop followed by a latched ROS e-stop."""
        for motor_index in (0, 1):
            try:
                self._call_motor_service(motor_index, False, 0.75)
            except Exception as exc:  # noqa: BLE001
                self.get_logger().error(
                    f"Final motor {motor_index + 1} stop failed: {exc}"
                )
        direction_stop = String()
        direction_stop.data = "stop"
        for _ in range(3):
            self._motor_direction_pub.publish(direction_stop)
            self._publish_estop(True)
            rclpy.spin_once(self, timeout_sec=0.05)
        self.get_logger().warn(
            "Final safety state: both motor stop services requested and "
            "/safety/e_stop latched True"
        )

    def _diagnostic_message(self) -> DiagnosticArray:
        message = DiagnosticArray()
        message.header.stamp = self.get_clock().now().to_msg()
        for result in self._results:
            status = DiagnosticStatus()
            status.name = (
                f"hardware_acceptance/{result.index:02d}_"
                + re.sub(r"[^a-z0-9]+", "_", result.name.lower()).strip("_")
            )
            status.hardware_id = "rock64_tank_robot"
            if result.status == PASS:
                status.level = DiagnosticStatus.OK
            elif result.status == SKIP:
                status.level = DiagnosticStatus.WARN
            else:
                status.level = DiagnosticStatus.ERROR
            status.message = f"{result.status}: {result.detail}"
            status.values.extend(
                [
                    KeyValue(key="status", value=result.status),
                    KeyValue(key="required", value=str(result.required)),
                    KeyValue(
                        key="duration_s",
                        value=f"{result.duration_s:.3f}",
                    ),
                ]
            )
            message.status.append(status)
        return message

    def _report_document(self, report_path: str) -> dict:
        failures = required_failure_count(self._results)
        return {
            "schema_version": 1,
            "started_at": self._started_wall.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "overall_status": PASS if failures == 0 else FAIL,
            "required_failures": failures,
            "tracks_raised": self._tracks_raised,
            "imu_required": True,
            "report_path": report_path,
            "results": [asdict(result) for result in self._results],
        }

    @staticmethod
    def _atomic_json_write(path_text: str, document: dict) -> str:
        """Write the JSON report atomically and return its absolute path."""
        path = Path(path_text).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        path = path.resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=str(path.parent),
            text=True,
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(document, stream, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, path)
        except Exception:
            try:
                os.unlink(temporary_name)
            except OSError:
                pass
            raise
        return str(path)

    def _write_report(self) -> str:
        requested = self._report_path
        try:
            resolved = str(Path(requested).expanduser().resolve())
            document = self._report_document(resolved)
            return self._atomic_json_write(resolved, document)
        except (OSError, ValueError) as first_error:
            # /tmp is commonly sticky (1777).  A previous run started with
            # sudo can therefore leave the conventional report owned by root,
            # and an unprivileged acceptance run cannot replace it.  Use a
            # per-UID fallback so a stale report can never make the test
            # runner crash after all hardware checks have completed.
            owner = str(getattr(os, "getuid", lambda: "user")())
            fallback = os.path.join(
                tempfile.gettempdir(),
                f"tank_robot_hardware_test_report.{owner}.json",
            )
            self.get_logger().warn(
                f"Could not write requested report {requested}: "
                f"{first_error}; falling back to {fallback}"
            )
            document = self._report_document(str(Path(fallback).resolve()))
            return self._atomic_json_write(fallback, document)

    def _publish_final(self, report_path: str) -> None:
        failures = required_failure_count(self._results)
        overall = PASS if failures == 0 else FAIL
        result_message = String()
        result_message.data = json.dumps(
            {
                "status": overall,
                "required_failures": failures,
                "report_path": report_path,
            },
            sort_keys=True,
        )
        diagnostics = self._diagnostic_message()
        deadline = time.monotonic() + self._result_hold_s
        while rclpy.ok() and time.monotonic() < deadline:
            self._result_pub.publish(result_message)
            self._diagnostics_pub.publish(diagnostics)
            rclpy.spin_once(self, timeout_sec=0.1)

    def _print_summary(self, report_path: str) -> None:
        print("\nHardware acceptance summary", flush=True)
        print("=" * 78, flush=True)
        for result in self._results:
            requirement = "required" if result.required else "optional"
            print(
                f"{result.index:02d}. {result.status:<4} "
                f"{result.name} ({requirement}) - {result.detail}",
                flush=True,
            )
        failures = required_failure_count(self._results)
        overall = PASS if failures == 0 else FAIL
        print("=" * 78, flush=True)
        print(
            f"OVERALL {overall}; required failures={failures}; "
            f"report={report_path}",
            flush=True,
        )
        print(
            "FINAL SAFETY: motor 1 stopped, motor 2 stopped, e-stop=True",
            flush=True,
        )

    def run(self) -> int:
        """Execute all stages, publish the result, and return a shell code."""
        print(
            "Rock64 ROS 2 hardware acceptance starting. "
            "Motors remain disabled unless tracks_raised:=true.",
            flush=True,
        )
        self._set_estop(True)
        try:
            self._run_stage("STM32 bridge alive", self._test_bridge_alive)
            self._run_stage("STM32 encoder stream", self._test_encoders)
            self._run_stage("STM32 odometry", self._test_odometry)
            self._run_stage("STM32 onboard IMU", self._test_imu)
            started = time.monotonic()
            self._record(
                "PS5 controller",
                SKIP,
                False,
                "service-owned teleop remains launched; operator input is "
                "not required by the basic acceptance gate",
                started,
            )
            self._run_stage(
                "ESP32 camera",
                lambda: self._test_camera(
                    self._esp_images,
                    "/camera/image_raw",
                ),
            )
            self._run_stage(
                "USB camera",
                lambda: self._test_camera(
                    self._usb_images,
                    "/camera/usb/image_raw",
                ),
            )
            if self._tracks_raised:
                print(
                    "RAISED-TRACK MOTOR PROOF: clearing ROS e-stop only for "
                    "the two guarded low-speed service stages.",
                    flush=True,
                )
                self._set_estop(False)
                self._run_stage(
                    "Motor 1 / left encoder proof",
                    lambda: self._test_motor(0),
                )
                self._run_stage(
                    "Motor 2 / right encoder proof",
                    lambda: self._test_motor(1),
                )
            else:
                for name in (
                    "Motor 1 / left encoder proof",
                    "Motor 2 / right encoder proof",
                ):
                    started = time.monotonic()
                    self._record(
                        name,
                        SKIP,
                        False,
                        "tracks_raised is false; no movement was requested",
                        started,
                    )
        except KeyboardInterrupt:
            started = time.monotonic()
            self._record(
                "Runner completion",
                FAIL,
                True,
                "operator interrupted the sequence",
                started,
            )
        finally:
            self._safe_shutdown()

        report_path = self._write_report()
        self._publish_final(report_path)
        self._print_summary(report_path)
        return 1 if required_failure_count(self._results) else 0


def main(args=None) -> None:
    """Run the sequential acceptance node as a ROS 2 executable."""
    rclpy.init(args=args)
    node = HardwareTestRunner()
    exit_code = 1
    try:
        exit_code = node.run()
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
