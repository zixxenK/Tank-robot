"""Pure helper tests for the sequential hardware acceptance runner."""

import json

from types import SimpleNamespace

import pytest

from robot_drivers.hardware_test_runner import (
    FAIL,
    HardwareTestRunner,
    PASS,
    StageResult,
    assess_motor_delta,
    bounded_servo_sequence,
    joy_has_operator_event,
    observe_image,
    parse_ps5_connected,
    required_failure_count,
    validate_encoder_values,
    validate_imu_values,
    validate_range_values,
)


def test_parse_ps5_connected_requires_explicit_true_state() -> None:
    """Connection parsing must not accept a merely present status topic."""
    assert parse_ps5_connected("connected=1 armed=1 mode=NORMAL")
    assert parse_ps5_connected("mode=NORMAL connected=true")
    assert not parse_ps5_connected("connected=0 armed=0 mode=NONE")
    assert not parse_ps5_connected("waiting for controller")


def test_ps5_operator_event_uses_change_not_trigger_rest_position() -> None:
    """A stable trigger value cannot masquerade as right-stick movement."""
    baseline_axes = (0.0, 0.0, 0.0, -1.0, -1.0)
    buttons = (0, 0, 0, 0)
    assert not joy_has_operator_event(
        baseline_axes,
        buttons,
        baseline_axes,
        buttons,
    )
    moved_axes = (0.0, 0.0, 0.5, -1.0, -1.0)
    assert joy_has_operator_event(
        baseline_axes,
        buttons,
        moved_axes,
        buttons,
    )
    assert joy_has_operator_event(
        baseline_axes,
        buttons,
        baseline_axes,
        (0, 0, 1, 0),
    )


def test_encoder_validation_requires_two_int32_values() -> None:
    """Encoder validation rejects missing and overflowing channel data."""
    assert validate_encoder_values((10, -20))[0]
    assert not validate_encoder_values((10,))[0]
    assert not validate_encoder_values((2**40, 0))[0]


def test_imu_validation_rejects_zero_nan_and_implausible_vectors() -> None:
    """A topic full of placeholder values must not pass the IMU stage."""
    assert validate_imu_values((0.0, 0.0, 9.81), (0.0, 0.0, 0.0))[0]
    assert not validate_imu_values((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))[0]
    assert not validate_imu_values(
        (float("nan"), 0.0, 9.81),
        (0.0, 0.0, 0.0),
    )[0]
    assert not validate_imu_values((0.0, 0.0, 100.0), (0.0, 0.0, 0.0))[0]


def test_ultrasonic_validation_requires_finite_in_range_echo() -> None:
    """NaN/no-echo and out-of-range HC-SR04 samples fail validation."""
    assert validate_range_values(0.75, 0.02, 4.0)[0]
    assert not validate_range_values(float("nan"), 0.02, 4.0)[0]
    assert not validate_range_values(4.5, 0.02, 4.0)[0]


def _image(stamp_ns: int, data_length: int = 18) -> SimpleNamespace:
    stamp = SimpleNamespace(
        sec=stamp_ns // 1_000_000_000,
        nanosec=stamp_ns % 1_000_000_000,
    )
    return SimpleNamespace(
        width=3,
        height=2,
        step=9,
        encoding="bgr8",
        data=bytes(data_length),
        header=SimpleNamespace(stamp=stamp),
    )


def test_image_observation_checks_stamp_dimensions_and_buffer() -> None:
    """Camera checks prove valid current frame payloads, not topic names."""
    valid = observe_image(_image(1_000_000_001))
    assert valid.valid
    assert valid.width == 3
    assert valid.height == 2

    assert not observe_image(_image(1_000_000_001, data_length=17)).valid
    assert not observe_image(_image(0)).valid


def test_servo_sequence_is_bounded_and_returns_to_center() -> None:
    """The command proof cannot request an angle outside SG90 bounds."""
    assert bounded_servo_sequence(90, 45, 135) == (
        90.0,
        45.0,
        135.0,
        90.0,
    )
    with pytest.raises(ValueError):
        bounded_servo_sequence(90, -1, 135)
    with pytest.raises(ValueError):
        bounded_servo_sequence(90, 20, 135)
    with pytest.raises(ValueError):
        bounded_servo_sequence(90, 100, 80)


def test_motor_delta_requires_correct_encoder_and_low_crosstalk() -> None:
    """A motor service response alone is not enough to pass motion proof."""
    passed, _ = assess_motor_delta((100, 200), (150, 203), 0, 5, 0.25)
    assert passed

    passed, _ = assess_motor_delta((100, 200), (102, 200), 0, 5, 0.25)
    assert not passed

    passed, _ = assess_motor_delta((100, 200), (150, 240), 0, 5, 0.25)
    assert not passed


def test_only_required_failures_change_process_result() -> None:
    """Optional failures and skips do not hide required hardware failures."""
    results = [
        StageResult(1, "required pass", PASS, True, "ok", 0.1),
        StageResult(2, "optional fail", FAIL, False, "missing", 0.1),
        StageResult(3, "required fail", FAIL, True, "missing", 0.1),
    ]
    assert required_failure_count(results) == 1


def test_json_report_write_is_atomic_and_readable(tmp_path) -> None:
    """The report helper leaves a complete JSON document at its target."""
    target = tmp_path / "nested" / "hardware.json"
    actual = HardwareTestRunner._atomic_json_write(
        str(target),
        {"overall_status": PASS, "results": []},
    )
    assert actual == str(target.resolve())
    assert target.read_text(encoding="utf-8").endswith("\n")
    assert json.loads(target.read_text(encoding="utf-8")) == {
        "overall_status": PASS,
        "results": [],
    }
