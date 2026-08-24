"""Tests for keyboard teleop's canonical tracked-drive limits."""

import pytest

from robot_teleop.keyboard_teleop import KeyboardTeleop


def test_keyboard_source_tree_uses_canonical_control_map() -> None:
    """Direct source-tree execution resolves the shared map."""
    node = KeyboardTeleop.__new__(KeyboardTeleop)
    control_map = node._load_control_map("/does/not/exist/control_map.yaml")

    assert control_map.track_width_m == pytest.approx(0.194)
    assert control_map.max_track_speed_mps == pytest.approx(0.8)


def test_keyboard_steering_limit_is_derived_from_track_geometry() -> None:
    """Keyboard steering uses the same full differential-drive ceiling."""
    node = KeyboardTeleop.__new__(KeyboardTeleop)
    control_map = node._load_control_map("/does/not/exist/control_map.yaml")
    max_angular = 2.0 * control_map.max_track_speed_mps / control_map.track_width_m

    assert max_angular == pytest.approx(8.2474226804)
