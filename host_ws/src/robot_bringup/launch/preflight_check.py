#!/usr/bin/env python3
# pylint: disable=import-error,no-member
"""Preflight checks for the canonical hardened STM32 bridge."""

import os

from launch.substitutions import LaunchConfiguration


def _as_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def preflight_or_raise(context, *args, **kwargs):
    """Reject hardware bringup when required Rock64 inputs are unavailable."""
    del args
    del kwargs

    use_hardware = _as_bool(
        LaunchConfiguration("use_hardware_bridge").perform(context)
    )
    if not use_hardware:
        return []

    serial_port = LaunchConfiguration("serial_port").perform(context).strip()
    if not serial_port:
        raise RuntimeError(
            "[rock64_bringup preflight] serial_port cannot be empty"
        )
    if not os.path.exists(serial_port):
        raise RuntimeError(
            "[rock64_bringup preflight] STM32 serial device does not exist: "
            + serial_port
        )

    use_teleop = _as_bool(
        LaunchConfiguration("use_teleop").perform(context)
    )
    if use_teleop:
        joy_device = LaunchConfiguration("joy_device").perform(context).strip()
        if not joy_device:
            raise RuntimeError(
                "[rock64_bringup preflight] joy_device cannot be empty"
            )
        # Note: Do not abort launch if joy_device is not yet connected.
        # ps5_ros_bridge includes dynamic hotplug detection and will auto-connect
        # as soon as the operator powers on the PS5 DualSense controller.

    return []
