#!/usr/bin/env python3
"""ps5_ros_bridge.py — DualSense (PS5) teleop bridge for the Hiwonder tracked chassis.

Command chain (confirmed live against github.com/zixxenK/Tank-robot @ 4ae83be):

    ps5_ros_bridge (/cmd_vel)
      -> safety_gateway.py (subscribes teleop_command_topic=/cmd_vel,
         clamps to max_linear_speed, max_angular_speed, requires a
         fresh message within teleop_command_timeout=0.25s — see
         host_ws/src/agent_core/config/safety_gateway.yaml)
      -> publishes /ranger/cmd_vel_safe
      -> stm32_hardened_bridge.py (_cmd_vel_callback subscribes
         /ranger/cmd_vel_safe, NOT /cmd_vel directly)
      -> USART1 PA9/PA10 @ 1,000,000 baud, /dev/rock64_stm32
         (docs/SOURCE_OF_TRUTH_1_0.md — frozen v1.0 transport)
      -> uart_binary_protocol_integration_packed.c -> encoder_motor.c PID

Physical chassis (docs/robot_hardware_reference.md §2, Hiwonder SKU 21030201
"Suspension Shock-Absorbing Tracked Chassis"):
    Track width (outer bracket)   : 0.194 m  (robot_control/control_map.yaml)
    Chassis length                 : 0.270 m
    Weight                         : 1.4 kg (single layer) / 1.6 kg (double layer)
    Drive motor                    : JGB3865-520R45-12, 12V (7-13V), rated 150±10 RPM output,
                                      rated torque 0.15 N*m, stall torque 0.5 N*m,
                                      stall current 1.5A (board caps driven current at 2A)
    Encoder                        : 11 PPR hall quadrature, motor shaft
    Layout                         : 2 drive motors total (left track, right track) — not 4WD

Motor/encoder contract:
    JGB3865-520R45-12 uses a 45:1 gearbox. With 11 PPR Hall quadrature counted
    on all 4 edges, rock64_hardware.yaml's encoder_ticks_per_rev is:

        11 pulses/rev * 4 edges/pulse * 45 = 1980 ticks/output-rev

Effective host-side speed ceiling actually enforced on the wire (NOT the
JGB520 PID hard clamp of 1.5 rps in encoder_motor.c:71, which never binds
because it is applied downstream of this one):
    uart_binary_protocol_integration_packed.c:127
        actual_rps = normalized_rps_command * MOTOR_DEFAULT_RPS_LIMIT   # 1.35 rps

wheel_radius (rock64_hardware.yaml) is still an explicit TODO — "Measure
actual wheel/sprocket radius" — currently 0.065 m placeholder. Every m/s
figure below inherits that uncertainty until it's measured with calipers.

    physical_max_linear_mps = wheel_radius * 2*pi * MOTOR_DEFAULT_RPS_LIMIT
                             = 0.065 * 2*pi * 1.35
                             ~= 0.551 m/s   (see enforce_physical_speed_ceiling below)

The shared control map first computes a normalized left/right track pair. The
pair is encoded as a standard physical ROS Twist before entering the safety
gateway. The hardened bridge decodes that Twist with the measured track width,
so the differential ratio survives the host safety path and remains correct
even when one track reverses during a power pivot.
"""

from __future__ import annotations

import os
import time
import math
from pathlib import Path
from typing import Optional

from robot_control.control_map import (
    ControlMap,
    DEFAULT_BUTTON_INDICES,
    DEFAULT_BUTTON_NAMES,
    DEFAULT_AXIS_PROFILES,
    TankDriveController,
    arcade_track_pair,
    default_control_map,
    load_control_map,
    shape_stick as shape_control_stick,
    track_pair_to_twist,
    trigger_pressure as control_trigger_pressure,
)

try:
    import rclpy
    from rclpy.node import Node
    from geometry_msgs.msg import Twist
    from sensor_msgs.msg import Joy
    from std_msgs.msg import Bool, String
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

    class _BoolFallback:
        def __init__(self, data=False):
            self.data = data

    class _StringFallback:
        def __init__(self, data=""):
            self.data = data

    class _JoyFallback:
        def __init__(self):
            self.axes = []
            self.buttons = []

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

        def create_subscription(self, _msg_type, _topic, _callback, _qos_profile):
            class _Subscription:
                pass

            return _Subscription()

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

        def ok(self):
            return False

    Twist = _TwistFallback
    Joy = _JoyFallback
    Bool = _BoolFallback
    String = _StringFallback
    Node = _NodeFallback
    rclpy = _FallbackRclpy()


def find_joystick_device(preferred_device: str = "/dev/input/js0") -> Optional[str]:
    """Find an available joystick device, checking preferred path first, then symlinks, then /dev/input/js*.

    Returns the absolute path to the joystick device node, or None if no controller is detected.
    """
    if preferred_device and preferred_device != "auto" and os.path.exists(preferred_device):
        return preferred_device

    # Check dedicated PS5 udev symlinks
    for symlink in ("/dev/input/ps5_controller", "/dev/input/ps5_controller_js"):
        if os.path.exists(symlink):
            return symlink

    # Check by-id entries for DualSense / PlayStation / Sony controllers
    by_id_dir = "/dev/input/by-id"
    if os.path.isdir(by_id_dir):
        try:
            for entry in sorted(os.listdir(by_id_dir)):
                entry_lower = entry.lower()
                if any(k in entry_lower for k in ("dualsense", "sony", "playstation", "wireless_controller")):
                    full_path = os.path.join(by_id_dir, entry)
                    if os.path.exists(full_path):
                        return full_path
        except OSError:
            pass

    # Check standard /dev/input/js* nodes
    if os.path.isdir("/dev/input"):
        try:
            js_nodes = sorted(
                [
                    os.path.join("/dev/input", f)
                    for f in os.listdir("/dev/input")
                    if f.startswith("js") and f[2:].isdigit()
                ]
            )
            if js_nodes:
                return js_nodes[0]
        except OSError:
            pass

    return None


def detect_device_profile(device_path: str) -> str:
    """Detect whether joystick device is connected via Bluetooth or USB."""
    try:
        resolved = os.path.realpath(device_path)
        dev_name = os.path.basename(resolved)
        sysfs_bustype = f"/sys/class/input/{dev_name}/device/id/bustype"
        if os.path.exists(sysfs_bustype):
            with open(sysfs_bustype, "r") as f:
                bustype = f.read().strip().lower()
                if bustype in ("0005", "5"):
                    return "ps5_bluetooth"
                if bustype in ("0003", "3"):
                    return "ps5_usb"
    except Exception:
        pass

    try:
        proc_devices = "/proc/bus/input/devices"
        if os.path.exists(proc_devices):
            with open(proc_devices, "r") as f:
                content = f.read()
                resolved_name = os.path.basename(os.path.realpath(device_path))
                for block in content.split("\n\n"):
                    if resolved_name in block or os.path.basename(device_path) in block:
                        if "Bus=0005" in block:
                            return "ps5_bluetooth"
                        if "Bus=0003" in block:
                            return "ps5_usb"
    except Exception:
        pass

    # Default to ps5_bluetooth layout on Linux for DualSense
    return "ps5_bluetooth"


class PS5RosBridge(Node):
    """Translates PS5 controller axes to Twist and publishes /cmd_vel.

    Layout:
    - Left stick vertical: Forward / Reverse throttle
    - Right stick horizontal: Left / Right steering
    - L2 trigger: Drift/power-pivot modifier (progressive pressure)
    - R2 trigger: Boost from the tuned 80% cruise to 100% top speed
    - L1 (hold): Precision mode — throttle/steer scaled by precision_mode_scale
    - R1 (hold): Boost mode — throttle/steer scaled by boost_mode_scale
    - L1/R1 + other button: reserved one-shot combo dispatch (_on_mode_combo)
    - SHARE: toggle armed/disarmed (only gates motion if require_arm_button=True)
    - OPTIONS: clear /safety/e_stop latch (publishes Bool(False))
    - PS: publish /safety/e_stop = True (hard stop through safety_gateway)
    """

    # Compatibility aliases; all indices and names are owned by the shared
    # robot_control map so teleop and accessory consumers cannot drift.
    BTN_CROSS = DEFAULT_BUTTON_INDICES["cross"]
    BTN_CIRCLE = DEFAULT_BUTTON_INDICES["circle"]
    BTN_TRIANGLE = DEFAULT_BUTTON_INDICES["triangle"]
    BTN_SQUARE = DEFAULT_BUTTON_INDICES["square"]
    BTN_L1 = DEFAULT_BUTTON_INDICES["l1"]
    BTN_R1 = DEFAULT_BUTTON_INDICES["r1"]
    BTN_L2_DIGITAL = DEFAULT_BUTTON_INDICES["l2_digital"]
    BTN_R2_DIGITAL = DEFAULT_BUTTON_INDICES["r2_digital"]
    BTN_SHARE = DEFAULT_BUTTON_INDICES["share"]
    BTN_OPTIONS = DEFAULT_BUTTON_INDICES["options"]
    BTN_PS = DEFAULT_BUTTON_INDICES["ps"]
    BTN_L3 = DEFAULT_BUTTON_INDICES["l3"]
    BTN_R3 = DEFAULT_BUTTON_INDICES["r3"]

    BUTTON_NAMES = DEFAULT_BUTTON_NAMES

    # Kept as a compatibility alias for integrations that inspect the node;
    # the values themselves live in robot_control/config/control_map.yaml.
    AXIS_PROFILES = DEFAULT_AXIS_PROFILES

    # motors_param.h: MOTOR_DEFAULT_RPS_LIMIT, applied in
    # uart_binary_protocol_integration_packed.c:127 before the per-motor PID
    # clamp ever sees the command — this is the real ceiling, not 1.5 rps.
    _FIRMWARE_RPS_CEILING = 1.35

    def __init__(self):
        super().__init__("ps5_ros_bridge")

        # Negative means use the canonical control-map geometry/speed.
        self.declare_parameter("max_linear_speed",  -1.0)
        # Kept for launch-file compatibility. The effective angular ceiling
        # is derived from the canonical track geometry below so drift cannot
        # be silently clipped by a stale independent parameter.
        self.declare_parameter("max_angular_speed", -1.0)
        self.declare_parameter("joy_device",        "/dev/input/js0")
        self.declare_parameter("joy_topic",         "/joy")
        self.declare_parameter("publish_joy",        True)
        self.declare_parameter("publish_rate_hz",   40.0)
        self.declare_parameter("deadzone",          -1.0)
        self.declare_parameter("expo",              -1.0)
        self.declare_parameter("trigger_deadzone",  -1.0)
        self.declare_parameter("reconnect_interval_s", 1.0)
        self.declare_parameter("profile",           "auto")  # auto, ps5_bluetooth, ps5_usb, custom
        self.declare_parameter("control_map_path",  "")
        self.declare_parameter("throttle_axis",     -1)  # -1 = use profile default
        self.declare_parameter("steer_axis",        -1)  # -1 = use profile default
        self.declare_parameter("drift_axis",        -1)  # -1 = use profile default
        self.declare_parameter("multiplier_axis",   -1)  # -1 = use profile default
        # The installed controller is mounted/oriented 180 degrees from the
        # original joydev sign convention; invert both stick axes by default.
        self.declare_parameter("invert_throttle",   True)
        self.declare_parameter("invert_steer",      True)

        # --- Physical-chassis parameters (docs/robot_hardware_reference.md,
        #     rock64_hardware.yaml). Informational + used only to derive the
        #     optional speed ceiling below; NOT used to reshape steering math.
        # Legacy geometry override; normal operation uses control_map.yaml.
        self.declare_parameter("track_width_m",      -1.0)
        self.declare_parameter("wheel_radius",       0.065)  # TODO unmeasured, see module docstring
        self.declare_parameter("encoder_ticks_per_rev", 1980)
        self.declare_parameter("firmware_rps_ceiling", self._FIRMWARE_RPS_CEILING)
        self.declare_parameter("enforce_physical_speed_ceiling", False)
        self.declare_parameter("drift_alpha", -1.0)
        self.declare_parameter("drift_beta", -1.0)

        # --- Mode-hold scaling (continuous, while button is held)
        self.declare_parameter("normal_mode_scale",    1.0)
        self.declare_parameter("precision_mode_scale", 0.4)
        self.declare_parameter("boost_mode_scale",     1.0)

        # --- Optional local safety features
        self.declare_parameter("require_arm_button",       False)
        self.declare_parameter("require_center_calibration", True)
        self.declare_parameter("publish_status",            True)
        self.declare_parameter("estop_topic",   "/safety/e_stop")
        self.declare_parameter("status_topic",  "/teleop/ps5_status")

        self._joy_dev = str(self.get_parameter("joy_device").value or "/dev/input/js0")
        self._joy_topic = str(self.get_parameter("joy_topic").value or "/joy")
        self._publish_joy_enabled = bool(self.get_parameter("publish_joy").value)
        rate_hz = float(self.get_parameter("publish_rate_hz").value or 40.0)
        self._reconnect_interval = float(
            self.get_parameter("reconnect_interval_s").value or 1.0
        )

        self._profile_param = str(self.get_parameter("profile").value or "auto").lower()
        control_map_path = str(self.get_parameter("control_map_path").value or "")
        self._control_map = self._load_control_map(control_map_path)
        self._apply_button_map()
        configured_max_lin = self._positive_float_parameter("max_linear_speed")
        self._max_lin = (
            configured_max_lin
            if configured_max_lin is not None
            else self._control_map.max_track_speed_mps
        )
        if configured_max_lin is not None and not math.isclose(
            configured_max_lin,
            self._control_map.max_track_speed_mps,
            rel_tol=1e-6,
            abs_tol=1e-6,
        ):
            self.get_logger().warn(
                "max_linear_speed is an explicit legacy override; tune the "
                "canonical robot_control control map for normal operation"
            )
        self._deadzone = self._map_float_parameter(
            "deadzone", self._control_map.deadzone
        )
        self._expo = self._map_float_parameter("expo", self._control_map.expo)
        self._trigger_deadzone = self._map_float_parameter(
            "trigger_deadzone", self._control_map.trigger_deadzone
        )
        self._trigger_neutral = self._control_map.trigger_neutral
        self._param_throttle = int(self.get_parameter("throttle_axis").value or -1)
        self._param_steer = int(self.get_parameter("steer_axis").value or -1)
        self._param_drift = int(self.get_parameter("drift_axis").value or -1)
        self._param_multiplier = int(self.get_parameter("multiplier_axis").value or -1)

        self._detected_profile = "ps5_bluetooth"
        self._apply_profile_axes(self._detected_profile)
        self._drive_controller = TankDriveController(
            self._control_map,
            profile_name=self._detected_profile,
            dt=1.0 / max(rate_hz, 1.0),
        )
        self._actual_joy_dev = None

        self._invert_throttle = bool(self.get_parameter("invert_throttle").value)
        self._invert_steer = bool(self.get_parameter("invert_steer").value)

        configured_track_width = self._positive_float_parameter("track_width_m")
        self._track_width = (
            configured_track_width
            if configured_track_width is not None
            else self._control_map.track_width_m
        )
        if (
            configured_track_width is not None
            and not math.isclose(
                configured_track_width,
                self._control_map.track_width_m,
                rel_tol=1e-6,
                abs_tol=1e-6,
            )
        ):
            self.get_logger().warn(
                "track_width_m is an explicit legacy override; tune the "
                "canonical robot_control control map for normal operation"
            )
        self._wheel_radius = float(self.get_parameter("wheel_radius").value or 0.065)
        self._ticks_per_rev = int(self.get_parameter("encoder_ticks_per_rev").value or 1980)
        self._firmware_rps_ceiling = float(
            self.get_parameter("firmware_rps_ceiling").value or self._FIRMWARE_RPS_CEILING
        )
        self._enforce_ceiling = bool(self.get_parameter("enforce_physical_speed_ceiling").value)

        configured_alpha = self._map_float_parameter(
            "drift_alpha", self._control_map.drift_alpha
        )
        configured_beta = self._map_float_parameter(
            "drift_beta", self._control_map.drift_beta
        )
        self._drift_alpha = max(0.0, min(1.0, configured_alpha))
        self._drift_beta = max(0.0, configured_beta)

        self._normal_scale = _clamp01(self.get_parameter("normal_mode_scale").value, 1.0)
        self._precision_scale = _clamp01(self.get_parameter("precision_mode_scale").value, 0.4)
        self._boost_scale = _clamp01(self.get_parameter("boost_mode_scale").value, 1.0)

        self._require_arm = bool(self.get_parameter("require_arm_button").value)
        self._require_calibration = bool(self.get_parameter("require_center_calibration").value)
        self._publish_status_enabled = bool(self.get_parameter("publish_status").value)
        self._estop_topic = str(self.get_parameter("estop_topic").value or "/safety/e_stop")
        self._status_topic = str(self.get_parameter("status_topic").value or "/teleop/ps5_status")

        # physical_max_linear_mps = wheel_radius * 2*pi * firmware_rps_ceiling
        self._physical_max_linear = (
            self._wheel_radius * 2.0 * 3.141592653589793 * self._firmware_rps_ceiling
        )
        if self._enforce_ceiling and self._max_lin > self._physical_max_linear > 0.0:
            self.get_logger().warn(
                f"max_linear_speed param ({self._max_lin:.3f} m/s) exceeds the "
                f"physically achievable ceiling derived from wheel_radius="
                f"{self._wheel_radius:.3f}m and firmware_rps_ceiling="
                f"{self._firmware_rps_ceiling:.2f} rps "
                f"({self._physical_max_linear:.3f} m/s). "
                "Clamping effective max_linear_speed to the physical ceiling; "
                "set enforce_physical_speed_ceiling:=false to override."
            )
            self._effective_max_lin = self._physical_max_linear
        else:
            self._effective_max_lin = self._max_lin

        self._max_track_speed = min(
            self._control_map.max_track_speed_mps,
            self._effective_max_lin,
        )
        configured_max_ang = self._positive_float_parameter("max_angular_speed")
        self._max_ang = (
            2.0 * self._max_track_speed / self._track_width
            if self._track_width > 0.0
            else 0.0
        )
        if (
            configured_max_ang is not None
            and not math.isclose(
                configured_max_ang,
                self._max_ang,
                rel_tol=1e-6,
                abs_tol=1e-6,
            )
        ):
            self.get_logger().warn(
                "max_angular_speed is derived from the canonical track "
                "geometry; the independent parameter is informational only"
            )

        self._pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self._joy_pub = (
            self.create_publisher(Joy, self._joy_topic, 10)
            if self._publish_joy_enabled
            else None
        )
        self._estop_pub = self.create_publisher(Bool, self._estop_topic, 10)
        self._status_pub = (
            self.create_publisher(String, self._status_topic, 10)
            if self._publish_status_enabled
            else None
        )
        self.create_subscription(
            Bool, self._estop_topic, self._on_estop_state, 10
        )

        self._axes = [0.0] * 16
        self._axis_ever_moved = [False] * 16
        self._axis_calibrated = [not self._require_calibration] * 16
        self._buttons = [0] * self._button_count
        self._last_reconnect_attempt = 0.0
        self._last_missing_log = 0.0
        self._last_calib_warn = 0.0
        self._armed = not self._require_arm
        self._estop_latched = False
        self._last_mode = "NORMAL"
        self._last_mode_combo = ""

        self._joy_fd = self._open_joystick(self._joy_dev)

        period = 1.0 / max(rate_hz, 1.0)
        self._timer = self.create_timer(period, self._publish_twist)
        self.get_logger().info(
            f"PS5 bridge started in standby — target device: {self._joy_dev}. "
            f"Physical speed ceiling: {self._effective_max_lin:.3f} m/s, max angular speed: {self._max_ang:.2f} rad/s. "
            "Auto-detection active: will dynamically connect when the PS5 controller powers on."
        )

    def _load_control_map(self, configured_path: str) -> ControlMap:
        """Load the canonical map, retaining a safe source-tree fallback."""
        candidates = []
        if configured_path:
            candidates.append(Path(configured_path))
        # In the source tree robot_control is a sibling package, not a
        # subdirectory of robot_teleop.  The launch graph normally supplies
        # the installed share path explicitly, but this fallback keeps direct
        # source-tree execution on the canonical YAML as well.
        candidates.append(
            Path(__file__).resolve().parents[2]
            / "robot_control"
            / "config"
            / "control_map.yaml"
        )
        try:
            from ament_index_python.packages import get_package_share_directory

            candidates.append(
                Path(get_package_share_directory("robot_control"))
                / "config"
                / "control_map.yaml"
            )
        except (ImportError, LookupError, RuntimeError):
            # Source-tree unit tests and non-ROS tooling do not have ament's
            # package index; the sibling-package candidate above is enough.
            pass
        for candidate in candidates:
            if not candidate.is_file():
                continue
            try:
                return load_control_map(candidate)
            except (OSError, ValueError, ImportError) as error:
                self.get_logger().warn(
                    f"Unable to load control map {candidate}: {error}"
                )
        self.get_logger().warn("Using built-in canonical PS5 control map")
        return default_control_map()

    def _map_float_parameter(self, name: str, default: float) -> float:
        """Use a finite explicit parameter or the canonical-map value."""
        value = self.get_parameter(name).value
        try:
            value = float(value)
        except (TypeError, ValueError):
            return default
        return default if value < 0.0 or not math.isfinite(value) else value

    def _apply_button_map(self) -> None:
        """Apply YAML button indices to the compatibility aliases at runtime.

        The class attributes retain the historical default aliases for code
        that imports them without constructing a node.  A running node must,
        however, use the loaded map so a commissioned controller layout is
        applied consistently to e-stop, mode buttons, audio, and raw Joy
        publication.
        """
        aliases = {
            "BTN_CROSS": "cross",
            "BTN_CIRCLE": "circle",
            "BTN_TRIANGLE": "triangle",
            "BTN_SQUARE": "square",
            "BTN_L1": "l1",
            "BTN_R1": "r1",
            "BTN_L2_DIGITAL": "l2_digital",
            "BTN_R2_DIGITAL": "r2_digital",
            "BTN_SHARE": "share",
            "BTN_OPTIONS": "options",
            "BTN_PS": "ps",
            "BTN_L3": "l3",
            "BTN_R3": "r3",
        }
        for attribute, key in aliases.items():
            setattr(self, attribute, int(self._control_map.button_indices[key]))
        self.BUTTON_NAMES = {
            int(index): str(name).upper()
            for name, index in self._control_map.button_indices.items()
        }
        self._button_count = max(
            32,
            max(self._control_map.button_indices.values(), default=31) + 1,
        )
        if hasattr(self, "_buttons") and len(self._buttons) < self._button_count:
            self._buttons.extend([0] * (self._button_count - len(self._buttons)))

    def _positive_float_parameter(self, name: str) -> Optional[float]:
        """Return a finite positive legacy override, if one was supplied."""
        try:
            value = float(self.get_parameter(name).value)
        except (TypeError, ValueError):
            return None
        return value if math.isfinite(value) and value > 0.0 else None

    def _apply_profile_axes(self, profile_name: str) -> None:
        """Apply mapped axes while retaining parameter override compatibility."""
        profile_defaults = self._control_map.profile(profile_name)
        self._throttle_axis = (
            self._param_throttle
            if self._param_throttle >= 0
            else profile_defaults["throttle_axis"]
        )
        self._steer_axis = (
            self._param_steer
            if self._param_steer >= 0
            else profile_defaults["steer_axis"]
        )
        self._drift_axis = (
            self._param_drift
            if self._param_drift >= 0
            else profile_defaults["drift_axis"]
        )
        self._multiplier_axis = (
            self._param_multiplier
            if self._param_multiplier >= 0
            else profile_defaults["multiplier_axis"]
        )
        if hasattr(self, "_drive_controller"):
            self._drive_controller.set_profile(profile_name)

    def _open_joystick(self, device: str):
        actual_dev = find_joystick_device(device)
        if not actual_dev:
            return None
        try:
            fd = open(actual_dev, "rb", buffering=0)  # noqa: SIM115
            self._actual_joy_dev = actual_dev
            self._axes = [0.0] * len(self._axes)
            self._axis_ever_moved = [False] * len(self._axis_ever_moved)
            self._axis_calibrated = [not self._require_calibration] * len(self._axis_calibrated)
            self._buttons = [0] * len(self._buttons)
            self._drive_controller.reset()

            # Detect profile dynamically on connection
            if self._profile_param == "auto":
                self._detected_profile = detect_device_profile(actual_dev)
            elif self._profile_param in self._control_map.axis_profiles:
                self._detected_profile = self._profile_param
            else:
                self._detected_profile = "ps5_bluetooth"

            self._apply_profile_axes(self._detected_profile)

            self.get_logger().info(
                f"PS5 controller connected on {actual_dev} (profile: {self._detected_profile}, "
                f"throttle: axis {self._throttle_axis}, steer: axis {self._steer_axis}, "
                f"L2 drift: axis {self._drift_axis}, R2 multiplier: axis {self._multiplier_axis}) — "
                "ready for operator use!"
            )
            return fd
        except OSError:
            return None

    def _on_estop_state(self, msg) -> None:
        """Mirror the real /safety/e_stop latch (may be set by other nodes)."""
        self._estop_latched = bool(msg.data)

    def _publish_estop(self, active: bool) -> None:
        msg = Bool()
        msg.data = bool(active)
        self._estop_pub.publish(msg)
        self._estop_latched = bool(active)

    def _handle_button_event(self, button_idx: int, pressed: bool):
        """Track button states, dispatch edge-triggered controls and combos."""
        if button_idx < 0 or button_idx >= len(self._buttons):
            return
        self._buttons[button_idx] = 1 if pressed else 0

        if not pressed:
            return

        if button_idx == self.BTN_PS:
            self.get_logger().warn("[PS] Emergency stop requested")
            self._publish_estop(True)
            return
        if button_idx == self.BTN_OPTIONS:
            self.get_logger().info("[OPTIONS] Clearing /safety/e_stop latch")
            self._publish_estop(False)
            return
        if button_idx == self.BTN_SHARE and self._require_arm:
            self._armed = not self._armed
            self.get_logger().info(f"[SHARE] {'ARMED' if self._armed else 'DISARMED'}")
            return

        # Check for mode combos when L1 or R1 is held as a modifier
        l1_held = bool(self._buttons[self.BTN_L1])
        r1_held = bool(self._buttons[self.BTN_R1])

        btn_name = self.BUTTON_NAMES.get(button_idx, f"BTN_{button_idx}")
        if l1_held and button_idx != self.BTN_L1:
            self.get_logger().info(f"[Mode Combo] L1 + {btn_name} triggered")
            self._on_mode_combo("L1", btn_name)
        elif r1_held and button_idx != self.BTN_R1:
            self.get_logger().info(f"[Mode Combo] R1 + {btn_name} triggered")
            self._on_mode_combo("R1", btn_name)

    def _on_mode_combo(self, modifier: str, action_button: str):
        """Record a one-shot modifier combo without issuing motion commands.

        Combos are intentionally status-only until a specific, reviewed
        action is assigned to one.  Previously this extension point silently
        discarded every event, which made controller commissioning and
        diagnostics impossible to verify.
        """
        combo = f"{str(modifier).upper()}+{str(action_button).upper()}"
        self._last_mode_combo = combo
        self.get_logger().info(
            f"[Mode Combo] {combo} recorded; no motion action is assigned"
        )
        if self._status_pub is not None:
            status = String()
            status.data = f"mode_combo={combo}"
            self._status_pub.publish(status)

    def _current_mode_scale(self) -> tuple[float, str]:
        """Continuous throttle/steer scale from L1 (precision) / R1 (boost)."""
        if self._buttons[self.BTN_L1]:
            return self._precision_scale, "PRECISION"
        if self._buttons[self.BTN_R1]:
            return self._boost_scale, "BOOST"
        return self._normal_scale, "NORMAL"

    def _read_joystick(self):
        """Non-blocking read of Linux joystick events (8 bytes each)."""
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
            while True:
                r, _, _ = select.select([self._joy_fd], [], [], 0)
                if not r:
                    break
                data = self._joy_fd.read(8)
                if not data or len(data) != 8:
                    break
                _, value, ev_type, number = struct.unpack("IhBB", data)
                # Ignore JS_EVENT_INIT synthetic events (0x80)
                is_init = bool(ev_type & 0x80)
                clean_type = ev_type & ~0x80

                if clean_type == 0x02:  # JS_EVENT_AXIS
                    if number < len(self._axes):
                        self._axes[number] = value / 32767.0
                        if not is_init:
                            self._axis_ever_moved[number] = True
                            if (
                                not self._axis_calibrated[number]
                                and abs(self._axes[number]) < self._deadzone
                            ):
                                self._axis_calibrated[number] = True
                elif clean_type == 0x01 and not is_init:  # JS_EVENT_BUTTON
                    self._handle_button_event(number, bool(value))
        except OSError:
            try:
                self._joy_fd.close()
            except OSError:
                pass
            self._joy_fd = None
            self._axes = [0.0] * len(self._axes)
            self._axis_ever_moved = [False] * len(self._axis_ever_moved)
            self._axis_calibrated = [not self._require_calibration] * len(self._axis_calibrated)
            self._buttons = [0] * len(self._buttons)
            self._drive_controller.reset()
            self.get_logger().warn(
                "PS5 controller disconnected; stopping motion and waiting for reconnection..."
            )

    def shape_stick(self, v: float) -> float:
        """Apply deadzone and cubic expo blend for smooth fine control."""
        return shape_control_stick(v, self._deadzone, self._expo)

    def get_trigger_pressure(self, axis_idx: int) -> float:
        """Read analog trigger pressure [0.0, 1.0] safely."""
        if axis_idx < 0 or axis_idx >= len(self._axes):
            return 0.0
        # If trigger has never sent a dynamic event, return 0.0 to prevent
        # starting up with phantom 50% brake from joydev resting at 0.
        if not self._axis_ever_moved[axis_idx]:
            return 0.0

        return control_trigger_pressure(
            self._axes[axis_idx],
            self._trigger_deadzone,
            self._trigger_neutral,
        )

    def calculate_velocities(
        self,
        throttle_input: float,
        steer_input: float,
        drift: float,
        multiplier: float,
    ) -> tuple[float, float]:
        """Convert the canonical PS5 inputs into a standard ROS Twist."""
        left, right = arcade_track_pair(
            throttle_input,
            steer_input,
            multiplier,
            drift,
            alpha=self._drift_alpha,
            beta=self._drift_beta,
            steering_gain=self._control_map.steering_gain,
            cruise_gain=self._control_map.cruise_gain,
        )
        return track_pair_to_twist(
            left,
            right,
            self._track_width,
            self._max_track_speed,
        )

    def _publish_twist(self):
        self._read_joystick()
        self._publish_joy_state()

        if self._joy_fd is None:
            self._drive_controller.reset()
            now = time.monotonic()
            if (now - self._last_missing_log) >= 10.0:
                self._last_missing_log = now
                self.get_logger().info(
                    "PS5 bridge waiting for controller connection..."
                )
            self._pub.publish(Twist())
            self._maybe_publish_status(
                connected=False, mode="NONE", drift=0.0, multiplier=0.0,
                lin=0.0, ang=0.0,
            )
            return

        # Apply the configured 180-degree controller orientation correction.
        raw_throttle = -self._axes[self._throttle_axis] if self._throttle_axis < len(self._axes) else 0.0
        if self._invert_throttle:
            raw_throttle = -raw_throttle
        throttle_cmd = self.shape_stick(raw_throttle)
        if self._require_calibration and not self._axis_calibrated[self._throttle_axis]:
            throttle_cmd = 0.0

        # Positive steering is the operator's right after orientation correction;
        # ROS angular.z is negative for that right turn.
        raw_steer = self._axes[self._steer_axis] if self._steer_axis < len(self._axes) else 0.0
        if self._invert_steer:
            raw_steer = -raw_steer
        steer_cmd = self.shape_stick(raw_steer)
        if self._require_calibration and not self._axis_calibrated[self._steer_axis]:
            steer_cmd = 0.0

        if self._require_calibration and self._joy_fd is not None:
            uncalibrated = (
                not self._axis_calibrated[self._throttle_axis]
                or not self._axis_calibrated[self._steer_axis]
            )
            now = time.monotonic()
            if uncalibrated and (now - self._last_calib_warn) >= 5.0:
                self._last_calib_warn = now
                self.get_logger().warn(
                    "Throttle/steer axis has not passed through center since "
                    "connect; holding that axis at zero until it does "
                    "(prevents a miscalibrated jsX resting value from "
                    "commanding motion). Center both sticks once."
                )

        scale, mode = self._current_mode_scale()
        self._last_mode = mode
        throttle_cmd *= scale
        steer_cmd *= scale

        # L2 is the drift brake and R2 boosts cruise speed from 80% to 100%.
        drift = self.get_trigger_pressure(self._drift_axis)
        multiplier = self.get_trigger_pressure(self._multiplier_axis)

        gate_open = self._armed and not self._estop_latched
        if not gate_open:
            throttle_cmd = 0.0
            steer_cmd = 0.0
            self._drive_controller.reset()

        if gate_open and throttle_cmd == 0.0 and steer_cmd == 0.0:
            # A centered controller must stop immediately; do not let the
            # track slew limiter leave residual motion after stick release.
            self._drive_controller.reset()
            lin_x, ang_z = 0.0, 0.0
        elif gate_open:
            left, right = self._drive_controller.update_values(
                throttle_cmd,
                steer_cmd,
                multiplier,
                drift,
            )
            lin_x, ang_z = track_pair_to_twist(
                left,
                right,
                self._track_width,
                self._max_track_speed,
            )
        else:
            lin_x, ang_z = 0.0, 0.0

        msg = Twist()
        msg.linear.x = float(lin_x)
        msg.angular.z = float(ang_z)
        self._pub.publish(msg)

        self._maybe_publish_status(
            connected=True, mode=mode, drift=drift, multiplier=multiplier,
            lin=lin_x, ang=ang_z,
        )

    def _publish_joy_state(self) -> None:
        """Publish raw controller state for audio and accessory consumers."""
        if self._joy_pub is None:
            return
        msg = Joy()
        msg.axes = list(self._axes)
        msg.buttons = list(self._buttons)
        self._joy_pub.publish(msg)

    def _maybe_publish_status(self, *, connected, mode, drift, multiplier, lin, ang) -> None:
        if self._status_pub is None:
            return
        msg = String()
        msg.data = (
            f"connected={int(connected)} armed={int(self._armed)} "
            f"estop={int(self._estop_latched)} mode={mode} "
            f"drift={drift:.2f} multiplier={multiplier:.2f} "
            f"lin={lin:.2f} ang={ang:.2f}"
        )
        self._status_pub.publish(msg)

    def destroy_node(self):
        if self._joy_fd:
            self._joy_fd.close()
        super().destroy_node()


def _clamp01(value, default: float) -> float:
    try:
        v = float(value) if value is not None else default
    except (TypeError, ValueError):
        v = default
    return max(0.0, min(1.0, v))


def main(args=None):
    rclpy.init(args=args)
    node = PS5RosBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        # launch can already shut down the context on SIGINT; avoid double shutdown.
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
