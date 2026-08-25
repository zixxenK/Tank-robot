"""Tests for the canonical DualSense tracked-drive mapping."""

import math

import pytest

from robot_control.control_map import (
    drift_track_pair,
    load_control_map,
    normalize_track_pair,
    track_pair_to_twist,
    twist_to_track_pair,
)


def test_checked_in_map_contains_approved_mapping() -> None:
    control_map = load_control_map("host_ws/src/robot_control/config/control_map.yaml")
    assert control_map.profile("ps5_bluetooth")["throttle_axis"] == 1
    assert control_map.profile("ps5_bluetooth")["steer_axis"] == 3
    assert control_map.profile("ps5_bluetooth")["drift_axis"] == 2
    assert control_map.profile("ps5_bluetooth")["multiplier_axis"] == 5
    assert control_map.drift_alpha == pytest.approx(0.9)
    assert control_map.drift_beta == pytest.approx(2.75)


def test_r2_release_removes_translation_but_not_steering() -> None:
    left, right = drift_track_pair(1.0, 1.0, 0.0, 0.0)
    assert left == pytest.approx(1.0)
    assert right > 0.0
    linear, angular = track_pair_to_twist(left, right, 0.194, 0.8)
    assert linear > 0.0
    assert angular < 0.0


def test_zero_to_one_trigger_neutral_is_really_released() -> None:
    from robot_control.control_map import trigger_pressure

    assert trigger_pressure(0.0, 0.08, released_at=0.0) == 0.0
    assert trigger_pressure(1.0, 0.08, released_at=0.0) == pytest.approx(1.0)


def test_full_drift_has_an_inside_track_reversal() -> None:
    left, right = drift_track_pair(1.0, 1.0, 1.0, 1.0)
    assert left > 0.0
    assert right < 0.0
    assert abs(left) <= 1.0
    assert abs(right) <= 1.0


def test_track_pair_and_twist_are_inverse_for_unsaturated_values() -> None:
    pair = (0.4, -0.2)
    twist = track_pair_to_twist(*pair, 0.194, 0.8)
    assert twist_to_track_pair(*twist, 0.194, 0.8) == pytest.approx(pair)


def test_normalization_rejects_nonfinite_values() -> None:
    assert normalize_track_pair(math.nan, 0.5) == (0.0, 0.0)
    assert normalize_track_pair(0.5, math.inf) == (0.0, 0.0)
