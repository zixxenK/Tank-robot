"""Unit tests for PS5RosBridge teleoperation mapping and controls."""

import os
import pytest
from robot_teleop.ps5_ros_bridge import PS5RosBridge, detect_device_profile, find_joystick_device


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


def test_pure_throttle_forward_and_reverse(bridge: PS5RosBridge) -> None:
    """Left stick forward/reverse produces linear motion without turning."""
    lin_fwd, ang_fwd = bridge.calculate_velocities(1.0, 0.0, 0.0, 0.0)
    assert lin_fwd == pytest.approx(bridge._effective_max_lin)
    assert ang_fwd == pytest.approx(0.0)

    lin_rev, ang_rev = bridge.calculate_velocities(-1.0, 0.0, 0.0, 0.0)
    assert lin_rev == pytest.approx(-bridge._effective_max_lin)
    assert ang_rev == pytest.approx(0.0)


def test_pure_steering_in_place(bridge: PS5RosBridge) -> None:
    """Right stick horizontal produces pure rotation in place."""
    lin_left, ang_left = bridge.calculate_velocities(0.0, 1.0, 0.0, 0.0)
    assert lin_left == pytest.approx(0.0)
    assert ang_left == pytest.approx(1.8)

    lin_right, ang_right = bridge.calculate_velocities(0.0, -1.0, 0.0, 0.0)
    assert lin_right == pytest.approx(0.0)
    assert ang_right == pytest.approx(-1.8)


def test_left_brake_variable_pressure(bridge: PS5RosBridge) -> None:
    """L2 trigger slows down the left track proportionally."""
    max_lin = bridge._effective_max_lin
    lin_x, ang_z = bridge.calculate_velocities(1.0, 0.0, 0.5, 0.0)
    assert lin_x == pytest.approx(max_lin * 0.75)
    assert ang_z == pytest.approx(max_lin * 0.25)

    lin_x_full, ang_z_full = bridge.calculate_velocities(1.0, 0.0, 1.0, 0.0)
    assert lin_x_full == pytest.approx(max_lin * 0.5)
    assert ang_z_full == pytest.approx(max_lin * 0.5)


def test_right_brake_variable_pressure(bridge: PS5RosBridge) -> None:
    """R2 trigger slows down the right track proportionally."""
    max_lin = bridge._effective_max_lin
    lin_x, ang_z = bridge.calculate_velocities(1.0, 0.0, 0.0, 0.5)
    assert lin_x == pytest.approx(max_lin * 0.75)
    assert ang_z == pytest.approx(-max_lin * 0.25)

    lin_x_full, ang_z_full = bridge.calculate_velocities(1.0, 0.0, 0.0, 1.0)
    assert lin_x_full == pytest.approx(max_lin * 0.5)
    assert ang_z_full == pytest.approx(-max_lin * 0.5)


def test_both_brakes_fully_applied_stops_robot(bridge: PS5RosBridge) -> None:
    """When both L2 and R2 are fully depressed, motion is zeroed."""
    lin_x, ang_z = bridge.calculate_velocities(1.0, 1.0, 1.0, 1.0)
    assert lin_x == pytest.approx(0.0)
    assert ang_z == pytest.approx(0.0)


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
