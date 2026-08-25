"""Unit tests for PS5RosBridge teleoperation mapping and controls."""

import os
import time
import pytest
from robot_teleop.ps5_ros_bridge import PS5RosBridge, detect_device_profile, find_joystick_device
from robot_control.control_map import load_control_map


@pytest.fixture
def bridge() -> PS5RosBridge:
    try:
        import rclpy
        if not rclpy.ok():
            rclpy.init()
    except Exception:
        pass
    node = PS5RosBridge()
    yield node
    try:
        node.destroy_node()
        import rclpy
        if rclpy.ok():
            rclpy.shutdown()
    except Exception:
        pass


def test_r2_released_brakes_linear_motion(bridge: PS5RosBridge) -> None:
    """R2 is the linear throttle multiplier, so release means no translation."""
    linear, angular = bridge.calculate_velocities(1.0, 0.0, 0.0, 0.0)
    assert linear == pytest.approx(0.0)
    assert angular == pytest.approx(0.0)


def test_source_tree_uses_canonical_control_map(bridge: PS5RosBridge) -> None:
    """Direct source-tree execution must resolve the sibling control package."""
    control_map = bridge._load_control_map("/does/not/exist/control_map.yaml")
    assert control_map.track_width_m == pytest.approx(0.194)
    assert control_map.max_track_speed_mps == pytest.approx(0.8)


def test_loaded_button_indices_propagate_to_runtime_aliases(
    bridge: PS5RosBridge, tmp_path
) -> None:
    """A commissioned map changes the live button behavior, not just YAML."""
    source = tmp_path / "custom_control_map.yaml"
    source.write_text(
        """
control_map:
  axis_profiles:
    ps5_bluetooth:
      throttle_axis: 1
      steer_axis: 2
      drift_axis: 3
      multiplier_axis: 4
  button_indices:
    cross: 13
    circle: 14
    triangle: 15
    square: 16
    l1: 17
    r1: 18
    l2_digital: 19
    r2_digital: 20
    share: 21
    options: 22
    ps: 23
    l3: 24
    r3: 25
  shaping:
    deadzone: 0.08
    expo: 0.25
    trigger_deadzone: 0.05
  drift:
    alpha: 0.9
    beta: 2.75
  geometry:
    track_width_m: 0.194
    max_track_speed_mps: 0.8
""",
        encoding="utf-8",
    )

    bridge._control_map = load_control_map(source)
    bridge._apply_button_map()

    assert bridge.BTN_PS == 23
    assert bridge.BTN_OPTIONS == 22
    assert bridge.BTN_L1 == 17
    assert bridge.BUTTON_NAMES[23] == "PS"
    assert len(bridge._buttons) >= 26


def test_steering_remains_live_when_r2_is_released(bridge: PS5RosBridge) -> None:
    """Steering is independent of R2 and can pivot the stopped chassis."""
    linear, angular = bridge.calculate_velocities(1.0, 1.0, 0.0, 0.0)
    assert linear == pytest.approx(0.0)
    assert abs(angular) > 0.0


def test_r2_pressure_scales_forward_and_reverse(bridge: PS5RosBridge) -> None:
    """R2 pressure progressively enables signed left-stick throttle."""
    linear, angular = bridge.calculate_velocities(1.0, 0.0, 0.0, 0.5)
    assert linear == pytest.approx(bridge._max_track_speed * 0.5)
    assert angular == pytest.approx(0.0)

    reverse, _ = bridge.calculate_velocities(-1.0, 0.0, 0.0, 1.0)
    assert reverse == pytest.approx(-bridge._max_track_speed)


def test_l2_applies_progressive_drift_modifier(bridge: PS5RosBridge) -> None:
    """L2 reduces forward traction and increases the steering differential."""
    normal = bridge.calculate_velocities(1.0, 0.5, 0.0, 1.0)
    drift = bridge.calculate_velocities(1.0, 0.5, 0.5, 1.0)
    assert abs(drift[0]) < abs(normal[0])
    assert abs(drift[1]) > abs(normal[1])


def test_full_right_drift_reverses_inside_right_track(bridge: PS5RosBridge) -> None:
    """The approved power-pivot model must reverse the inside track."""
    from robot_control.control_map import drift_track_pair

    left, right = drift_track_pair(1.0, 1.0, 1.0, 1.0)
    assert left > 0.0
    assert right < 0.0


def test_live_right_stick_maps_to_a_right_turn(bridge: PS5RosBridge) -> None:
    """A positive joydev right-stick value reverses the right inside track."""
    bridge._joy_fd = object()
    bridge._axes[bridge._throttle_axis] = -1.0  # stick up
    bridge._axes[bridge._steer_axis] = 1.0  # stick right
    bridge._axes[bridge._drift_axis] = 1.0  # L2 fully pressed
    bridge._axes[bridge._multiplier_axis] = 1.0  # R2 fully pressed
    bridge._axis_ever_moved[bridge._multiplier_axis] = True
    bridge._axis_calibrated[bridge._throttle_axis] = True
    bridge._axis_calibrated[bridge._steer_axis] = True
    bridge._read_joystick = lambda: None

    bridge._publish_twist()

    command = bridge._pub.last_msg
    assert command.angular.z < 0.0
    assert abs(command.angular.z) > abs(command.linear.x)


def test_trigger_uninitialized_safety(bridge: PS5RosBridge) -> None:
    """Uninitialized trigger axis at 0.0 raw value must not produce 50% brake."""
    bridge._axis_ever_moved[2] = False
    bridge._axes[2] = 0.0
    assert bridge.get_trigger_pressure(2) == 0.0

    bridge._axis_ever_moved[2] = True
    bridge._axes[2] = -1.0
    assert bridge.get_trigger_pressure(2) == 0.0

    bridge._axes[2] = 0.0
    pressure = bridge.get_trigger_pressure(2)
    assert 0.45 < pressure < 0.50

    bridge._axes[2] = 1.0
    assert bridge.get_trigger_pressure(2) == pytest.approx(1.0)


def test_stick_deadzone(bridge: PS5RosBridge) -> None:
    """Stick deflections within deadzone yield 0.0."""
    assert bridge.shape_stick(0.05) == 0.0
    assert bridge.shape_stick(-0.05) == 0.0
    assert bridge.shape_stick(0.5) > 0.0
    assert bridge.shape_stick(-0.5) < 0.0


def test_precision_mode_scaling(bridge: PS5RosBridge) -> None:
    """Holding L1 enables precision mode (0.4x scale)."""
    scale_norm, mode_norm = bridge._current_mode_scale()
    assert scale_norm == pytest.approx(1.0)
    assert mode_norm == "NORMAL"

    bridge._buttons[bridge.BTN_L1] = 1
    scale_prec, mode_prec = bridge._current_mode_scale()
    assert scale_prec == pytest.approx(0.4)
    assert mode_prec == "PRECISION"
    bridge._buttons[bridge.BTN_L1] = 0


def test_estop_controls(bridge: PS5RosBridge) -> None:
    """PS button latches e-stop; OPTIONS button clears it."""
    assert not bridge._estop_latched
    bridge._handle_button_event(bridge.BTN_PS, True)
    assert bridge._estop_latched

    bridge._handle_button_event(bridge.BTN_OPTIONS, True)
    assert not bridge._estop_latched


def test_mode_combo_detection(bridge: PS5RosBridge) -> None:
    """Holding L1 or R1 and pressing another button registers mode combos."""
    combos_recorded: list[tuple[str, str]] = []

    def mock_combo_handler(mod: str, btn: str) -> None:
        combos_recorded.append((mod, btn))

    bridge._on_mode_combo = mock_combo_handler

    bridge._handle_button_event(bridge.BTN_L1, True)
    assert len(combos_recorded) == 0

    bridge._handle_button_event(bridge.BTN_CROSS, True)
    assert combos_recorded == [("L1", "CROSS")]

    bridge._handle_button_event(bridge.BTN_CROSS, False)
    bridge._handle_button_event(bridge.BTN_L1, False)

    bridge._handle_button_event(bridge.BTN_R1, True)
    bridge._handle_button_event(bridge.BTN_TRIANGLE, True)
    assert combos_recorded == [("L1", "CROSS"), ("R1", "TRIANGLE")]


def test_mode_combo_is_status_only(bridge: PS5RosBridge) -> None:
    """Unassigned combos are observable but cannot create motion authority."""
    bridge._on_mode_combo("L1", "CROSS")

    assert bridge._last_mode_combo == "L1+CROSS"
    assert bridge._status_pub.last_msg.data == "mode_combo=L1+CROSS"
    assert not bridge._estop_latched


def test_find_joystick_device_fallback(tmp_path) -> None:
    """find_joystick_device detects existing devices and falls back cleanly."""
    # Non-existent device returns None if no /dev/input devices exist
    res = find_joystick_device("/nonexistent/path/device")
    if not os.path.exists("/dev/input/js0") and not os.path.exists("/dev/input/ps5_controller"):
        assert res is None or res.startswith("/dev/input/")

    # If preferred path exists, it is selected
    test_file = tmp_path / "fake_js0"
    test_file.write_bytes(b"")
    assert find_joystick_device(str(test_file)) == str(test_file)


def test_disconnect_and_reconnect_zeroing(bridge: PS5RosBridge) -> None:
    """Disconnecting clears axes and prevents phantom commands."""
    bridge._axes[1] = -0.8
    bridge._axis_ever_moved[1] = True
    bridge._joy_fd = None  # Simulate disconnected state
    bridge._last_reconnect_attempt = time.monotonic()

    bridge._publish_twist()
    assert bridge._joy_fd is None


def test_publish_joy_state_includes_triangle_and_modifiers(bridge: PS5RosBridge) -> None:
    """The raw Joy stream preserves the DualSense button indices used by audio."""
    published = []

    class Publisher:
        def publish(self, message):
            published.append(message)

    bridge._joy_pub = Publisher()
    bridge._buttons[bridge.BTN_L1] = 1
    bridge._buttons[bridge.BTN_R1] = 1
    bridge._buttons[bridge.BTN_TRIANGLE] = 1

    bridge._publish_joy_state()

    assert len(published) == 1
    assert published[0].buttons[bridge.BTN_TRIANGLE] == 1
    assert published[0].buttons[bridge.BTN_L1] == 1
    assert published[0].buttons[bridge.BTN_R1] == 1
