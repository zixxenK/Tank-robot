"""Canonical DualSense control mapping and tracked-drive math.

The controller produces a normalized pair of left/right track demands.  ROS
continues to use a normal ``geometry_msgs/Twist`` at package boundaries; the
conversion here is the only place that translates between the two forms.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence, Union

import math


DEFAULT_AXIS_PROFILES = {
    "ps5_bluetooth": {
        "throttle_axis": 1,
        "steer_axis": 3,
        "drift_axis": 2,
        "multiplier_axis": 5,
    },
    "ps5_usb": {
        "throttle_axis": 1,
        "steer_axis": 3,
        "drift_axis": 2,
        "multiplier_axis": 5,
    },
}

DEFAULT_BUTTON_INDICES = {
    "cross": 0,
    "circle": 1,
    "triangle": 2,
    "square": 3,
    "l1": 4,
    "r1": 5,
    "l2_digital": 6,
    "r2_digital": 7,
    "share": 8,
    "options": 9,
    "ps": 10,
    "l3": 11,
    "r3": 12,
}

REQUIRED_BUTTON_KEYS = frozenset(DEFAULT_BUTTON_INDICES)
REQUIRED_AXIS_KEYS = frozenset(
    ("throttle_axis", "steer_axis", "drift_axis", "multiplier_axis")
)

DEFAULT_BUTTON_NAMES = {
    index: name.upper() for name, index in DEFAULT_BUTTON_INDICES.items()
}


@dataclass(frozen=True)
class ControlMap:
    """Validated values from the canonical control-map YAML file."""

    axis_profiles: Mapping[str, Mapping[str, int]]
    button_indices: Mapping[str, int]
    deadzone: float
    expo: float
    trigger_deadzone: float
    trigger_neutral: float
    drift_alpha: float
    drift_beta: float
    track_width_m: float
    max_track_speed_mps: float
    steering_gain: float = 0.7
    cruise_gain: float = 0.5
    track_slew_per_s: float = 4.0

    def profile(self, name: str) -> Mapping[str, int]:
        """Return a named axis profile, falling back to Bluetooth layout."""
        return self.axis_profiles.get(
            name,
            self.axis_profiles.get("ps5_bluetooth", {}),
        )


def default_control_map() -> ControlMap:
    """Return the checked-in canonical map when a ROS share path is absent."""
    return ControlMap(
        axis_profiles=DEFAULT_AXIS_PROFILES,
        button_indices=DEFAULT_BUTTON_INDICES,
        deadzone=0.08,
        expo=0.25,
        trigger_deadzone=0.05,
        trigger_neutral=0.0,
        drift_alpha=0.9,
        drift_beta=2.75,
        track_width_m=0.194,
        max_track_speed_mps=0.8,
        steering_gain=0.7,
        cruise_gain=0.8,
        track_slew_per_s=10.0,
    )


def _finite_float(data: Mapping[str, Any], key: str, default: float) -> float:
    value = float(data.get(key, default))
    if not math.isfinite(value):
        raise ValueError(f"control-map value {key!r} must be finite")
    return value


def load_control_map(path: Union[str, Path]) -> ControlMap:
    """Load and validate the shared control-map YAML file."""
    import yaml

    source = Path(path)
    with source.open("r", encoding="utf-8") as stream:
        document = yaml.safe_load(stream) or {}
    root = document.get("control_map", document)
    if not isinstance(root, Mapping):
        raise ValueError("control-map YAML must contain a mapping")

    raw_profiles = root.get("axis_profiles", {})
    if not isinstance(raw_profiles, Mapping) or not raw_profiles:
        raise ValueError("control-map must define axis_profiles")
    profiles: dict[str, dict[str, int]] = {}
    for profile_name, raw_profile in raw_profiles.items():
        if not isinstance(raw_profile, Mapping):
            raise ValueError(f"axis profile {profile_name!r} must be a mapping")
        profile = {
            key: int(raw_profile[key])
            for key in REQUIRED_AXIS_KEYS
            if key in raw_profile
        }
        if set(profile) != REQUIRED_AXIS_KEYS:
            raise ValueError(f"axis profile {profile_name!r} is incomplete")
        for key in ("dpad_x_axis", "dpad_y_axis"):
            if key in raw_profile:
                profile[key] = int(raw_profile[key])
        if any(value < 0 for value in profile.values()):
            raise ValueError(
                f"axis profile {profile_name!r} contains a negative index"
            )
        profiles[str(profile_name)] = profile

    if "ps5_bluetooth" not in profiles:
        raise ValueError("control-map must define the ps5_bluetooth axis profile")

    raw_buttons = root.get("button_indices", {})
    if not isinstance(raw_buttons, Mapping):
        raise ValueError("button_indices must be a mapping")
    missing_buttons = REQUIRED_BUTTON_KEYS.difference(raw_buttons)
    if missing_buttons:
        missing = ", ".join(sorted(missing_buttons))
        raise ValueError(f"control-map is missing required button indices: {missing}")
    buttons: dict[str, int] = {}
    for key, value in raw_buttons.items():
        try:
            index = int(value)
        except (TypeError, ValueError) as error:
            raise ValueError(f"button index {key!r} must be an integer") from error
        if index < 0:
            raise ValueError(f"button index {key!r} must be non-negative")
        buttons[str(key)] = index
    if len(buttons.values()) != len(set(buttons.values())):
        raise ValueError("button_indices must not assign the same index twice")

    drift = root.get("drift", {})
    geometry = root.get("geometry", {})
    shaping = root.get("shaping", {})
    throttle_cfg = root.get("throttle", {})
    smoothing = root.get("smoothing", {})
    if not isinstance(drift, Mapping) or not isinstance(geometry, Mapping):
        raise ValueError("drift and geometry must be mappings")
    if not isinstance(shaping, Mapping):
        raise ValueError("shaping must be a mapping")
    if not isinstance(throttle_cfg, Mapping) or not isinstance(smoothing, Mapping):
        raise ValueError("throttle and smoothing must be mappings")

    result = ControlMap(
        axis_profiles=profiles,
        button_indices=buttons,
        deadzone=_finite_float(shaping, "deadzone", 0.05),
        expo=_finite_float(shaping, "expo", 0.15),
        trigger_deadzone=_finite_float(shaping, "trigger_deadzone", 0.08),
        trigger_neutral=_finite_float(shaping, "trigger_neutral", 0.0),
        drift_alpha=_finite_float(drift, "alpha", 0.9),
        drift_beta=_finite_float(drift, "beta", 2.75),
        track_width_m=_finite_float(geometry, "track_width_m", 0.194),
        max_track_speed_mps=_finite_float(
            geometry, "max_track_speed_mps", 0.8
        ),
        steering_gain=_finite_float(shaping, "steering_gain", 0.7),
        cruise_gain=_finite_float(throttle_cfg, "cruise_gain", 0.8),
        track_slew_per_s=_finite_float(smoothing, "track_slew_per_s", 10.0),
    )
    if not 0.0 <= result.deadzone < 1.0:
        raise ValueError("deadzone must be in [0, 1)")
    if not 0.0 <= result.trigger_deadzone < 1.0:
        raise ValueError("trigger_deadzone must be in [0, 1)")
    if not -1.0 <= result.trigger_neutral < 1.0:
        raise ValueError("trigger_neutral must be in [-1, 1)")
    if not 0.0 <= result.expo <= 1.0:
        raise ValueError("expo must be in [0, 1]")
    if not 0.0 <= result.drift_alpha <= 1.0:
        raise ValueError("drift alpha must be in [0, 1]")
    if result.drift_beta < 0.0:
        raise ValueError("drift beta must be non-negative")
    if not 0.0 <= result.steering_gain <= 1.0:
        raise ValueError("steering_gain must be in [0, 1]")
    if result.track_width_m <= 0.0 or result.max_track_speed_mps <= 0.0:
        raise ValueError("track geometry values must be positive")
    if not 0.0 <= result.cruise_gain <= 1.0:
        raise ValueError("cruise_gain must be in [0, 1]")
    if result.track_slew_per_s <= 0.0:
        raise ValueError("track_slew_per_s must be positive")
    return result


def shape_stick(value: float, deadzone: float, expo: float) -> float:
    """Apply a symmetric deadzone and cubic expo curve."""
    value = float(value)
    if not math.isfinite(value):
        return 0.0
    value = max(-1.0, min(1.0, value))
    if abs(value) < deadzone:
        return 0.0
    scaled = (abs(value) - deadzone) / max(1.0 - deadzone, 1e-9)
    shaped = (1.0 - expo) * scaled + expo * (scaled**3)
    return math.copysign(min(1.0, shaped), value)


def trigger_pressure(
    raw: float,
    deadzone: float = 0.05,
    released_at: float = -1.0,
) -> float:
    """Convert a joydev trigger using its configured released position.

    Some Linux DualSense joydev layouts expose triggers as ``0..+1`` while
    older layouts expose them as ``-1..+1``.  Keeping the released position
    explicit prevents an idle trigger from becoming a phantom half-press.
    """
    raw = float(raw)
    released_at = float(released_at)
    if not math.isfinite(raw) or not math.isfinite(released_at):
        return 0.0
    if released_at >= 1.0:
        return 0.0
    normalized = max(
        0.0,
        min(1.0, (raw - released_at) / max(1.0 - released_at, 1e-9)),
    )
    if normalized < deadzone:
        return 0.0
    return max(
        0.0,
        min(1.0, (normalized - deadzone) / max(1.0 - deadzone, 1e-9)),
    )


def normalize_track_pair(left: float, right: float) -> tuple[float, float]:
    """Clamp a track pair together while preserving its differential ratio."""
    left = float(left)
    right = float(right)
    if not math.isfinite(left) or not math.isfinite(right):
        return 0.0, 0.0
    scale = max(1.0, abs(left), abs(right))
    return left / scale, right / scale


def drift_track_pair(
    throttle: float,
    steering: float,
    multiplier: float,
    drift: float,
    alpha: float = 0.9,
    beta: float = 2.75,
) -> tuple[float, float]:
    """Compatibility mixer with an explicit full-speed multiplier.

    New split-stick callers should use :func:`arcade_track_pair`, which applies
    the configured 50--100% cruise/boost gain.  Keeping this helper preserves
    the older low-level API used by bridge and unit-test integrations.
    """
    return arcade_track_pair(
        throttle,
        steering,
        multiplier,
        drift,
        alpha=alpha,
        beta=beta,
        steering_gain=0.7,
        cruise_gain=1.0,
    )


def arcade_track_pair(
    throttle: float,
    steering: float,
    boost: float,
    drift: float,
    alpha: float = 0.9,
    beta: float = 2.75,
    steering_gain: float = 0.7,
    cruise_gain: float = 0.5,
) -> tuple[float, float]:
    """Return normalized track demands for split-stick arcade drive.

    R2 changes the throttle gain from ``cruise_gain`` (released) to 1.0
    (fully pressed). L2 reduces forward momentum while turning and increases
    the turn component, producing the requested handbrake/pivot behavior.
    """
    values = tuple(
        float(value)
        for value in (throttle, steering, boost, drift, steering_gain, cruise_gain)
    )
    if not all(math.isfinite(value) for value in values):
        return 0.0, 0.0
    throttle, steering, boost, drift, steering_gain, cruise_gain = values
    throttle = max(-1.0, min(1.0, throttle))
    steering = max(-1.0, min(1.0, steering))
    boost = max(0.0, min(1.0, boost))
    drift = max(0.0, min(1.0, drift))
    steering_gain = max(0.0, min(1.0, steering_gain))
    cruise_gain = max(0.0, min(1.0, cruise_gain))
    gain = cruise_gain + (1.0 - cruise_gain) * boost
    traction = throttle * gain
    forward_component = traction * (1.0 - alpha * drift * abs(steering))
    # Normal steering remains car-like: L2 is required before the inside
    # track reverses. This avoids an abrupt, sloppy pivot during ordinary
    # driving while preserving the requested handbrake turn.
    turn_gain = steering_gain + (1.0 - steering_gain) * drift
    turn_component = steering * turn_gain * (1.0 + beta * drift)
    return (
        max(-1.0, min(1.0, forward_component + turn_component)),
        max(-1.0, min(1.0, forward_component - turn_component)),
    )


@dataclass
class SlewLimiter:
    """Rate-limit one normalized track command between control ticks."""

    max_delta_per_call: float
    value: float = 0.0

    def step(self, target: float) -> float:
        target = max(-1.0, min(1.0, float(target)))
        delta = target - self.value
        if abs(delta) > self.max_delta_per_call:
            delta = math.copysign(self.max_delta_per_call, delta)
        self.value += delta
        return self.value

    def reset(self, value: float = 0.0) -> None:
        self.value = max(-1.0, min(1.0, float(value)))


@dataclass
class TankDriveController:
    """Shared stateful split-stick mixer used by the PS5 runtime."""

    control_map: ControlMap
    profile_name: str = "ps5_bluetooth"
    dt: float = 1.0 / 30.0

    def __post_init__(self) -> None:
        self._profile = self.control_map.profile(self.profile_name)
        max_delta = max(self.control_map.track_slew_per_s * self.dt, 1e-6)
        self._left = SlewLimiter(max_delta)
        self._right = SlewLimiter(max_delta)

    def set_profile(self, profile_name: str) -> None:
        self.profile_name = profile_name
        self._profile = self.control_map.profile(profile_name)

    def reset(self) -> None:
        self._left.reset()
        self._right.reset()

    def update_values(
        self,
        throttle: float,
        steering: float,
        boost: float,
        drift: float,
    ) -> tuple[float, float]:
        """Mix already-shaped inputs and return slew-limited tracks."""
        left, right = arcade_track_pair(
            throttle,
            steering,
            boost,
            drift,
            alpha=self.control_map.drift_alpha,
            beta=self.control_map.drift_beta,
            steering_gain=self.control_map.steering_gain,
            cruise_gain=self.control_map.cruise_gain,
        )
        return self._left.step(left), self._right.step(right)

    def update(self, axes: Sequence[float]) -> tuple[float, float]:
        """Consume a raw joydev frame using the canonical axis profile."""
        profile = self._profile
        # Match the mounted controller's 180-degree orientation correction
        # used by the PS5 ROS bridge.
        raw_throttle = float(axes[profile["throttle_axis"]])
        raw_steer = -float(axes[profile["steer_axis"]])
        throttle = shape_stick(raw_throttle, self.control_map.deadzone, self.control_map.expo)
        steering = shape_stick(raw_steer, self.control_map.deadzone, self.control_map.expo)
        boost = trigger_pressure(
            float(axes[profile["multiplier_axis"]]),
            self.control_map.trigger_deadzone,
            self.control_map.trigger_neutral,
        )
        drift = trigger_pressure(
            float(axes[profile["drift_axis"]]),
            self.control_map.trigger_deadzone,
            self.control_map.trigger_neutral,
        )
        return self.update_values(throttle, steering, boost, drift)


def track_pair_to_twist(
    left: float,
    right: float,
    track_width_m: float,
    max_track_speed_mps: float,
) -> tuple[float, float]:
    """Encode normalized tracks as a standard linear/angular ROS command.

    ROS ``angular.z`` is positive for a left/CCW turn, so a right-turn pair
    with the right track slower or reversing produces a negative angular value.
    """
    if (
        not math.isfinite(float(track_width_m))
        or not math.isfinite(float(max_track_speed_mps))
        or track_width_m <= 0.0
        or max_track_speed_mps <= 0.0
    ):
        return 0.0, 0.0
    left, right = normalize_track_pair(left, right)
    left_mps = left * max_track_speed_mps
    right_mps = right * max_track_speed_mps
    return (
        (left_mps + right_mps) / 2.0,
        (right_mps - left_mps) / track_width_m,
    )


def twist_to_track_pair(
    linear_mps: float,
    angular_rps: float,
    track_width_m: float,
    max_track_speed_mps: float,
) -> tuple[float, float]:
    """Decode a standard ROS command into normalized track demands."""
    if (
        not math.isfinite(float(linear_mps))
        or not math.isfinite(float(angular_rps))
        or not math.isfinite(float(track_width_m))
        or not math.isfinite(float(max_track_speed_mps))
        or track_width_m <= 0.0
        or max_track_speed_mps <= 0.0
    ):
        return 0.0, 0.0
    half_width = track_width_m / 2.0
    left_mps = float(linear_mps) - float(angular_rps) * half_width
    right_mps = float(linear_mps) + float(angular_rps) * half_width
    return normalize_track_pair(
        left_mps / max_track_speed_mps,
        right_mps / max_track_speed_mps,
    )
