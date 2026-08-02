#!/usr/bin/env python3
# pylint: disable=import-error,no-member
"""Preflight checks for the canonical hardened STM32 bridge."""

import os

from launch.substitutions import LaunchConfiguration


def _as_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def preflight_or_raise(context, *args, **kwargs):
    """Reject hardware bringup when its serial device is unavailable."""
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

    return []
