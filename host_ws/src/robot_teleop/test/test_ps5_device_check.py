"""Tests for the PS5 readiness-check command line."""

from robot_teleop.ps5_device_check import build_parser


def test_legacy_device_option_is_accepted() -> None:
    """The operator procedure's historical --device spelling remains valid."""
    args = build_parser().parse_args(["--device", "/dev/input/js0"])

    assert args.joy_device == "/dev/input/js0"
