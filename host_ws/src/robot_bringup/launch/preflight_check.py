#!/usr/bin/env python3
"""Preflight validation for rock64 bringup launch.

Raises RuntimeError when selected control mode and serial-device availability
are inconsistent, so launch stops before starting runtime nodes.
"""

from __future__ import annotations

import os

from launch.substitutions import LaunchConfiguration


def _as_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _exists(path: str) -> bool:
    return bool(path) and os.path.exists(path)


def preflight_or_raise(context, *args, **kwargs):
    del args
    del kwargs

    use_micro_ros = _as_bool(
        LaunchConfiguration("use_micro_ros").perform(context)
    )
    use_legacy_bridges = _as_bool(
        LaunchConfiguration("use_legacy_bridges").perform(context)
    )
    allow_mixed_bridges = _as_bool(
        LaunchConfiguration("allow_mixed_bridges").perform(context)
    )

    micro_ros_transport = LaunchConfiguration("micro_ros_transport").perform(
        context
    ).strip()
    micro_ros_dev = (
        LaunchConfiguration("micro_ros_dev").perform(context).strip()
    )
    serial_port = LaunchConfiguration("serial_port").perform(context).strip()

    errors = []

    if not use_micro_ros and not use_legacy_bridges:
        errors.append(
            "Invalid mode selection: both use_micro_ros and "
            "use_legacy_bridges are false."
        )

    if use_micro_ros and use_legacy_bridges and not allow_mixed_bridges:
        errors.append(
            "Invalid mode selection: both use_micro_ros and "
            "use_legacy_bridges are true while allow_mixed_bridges is false."
        )

    if use_micro_ros:
        if micro_ros_transport not in {"serial", "udp4"}:
            errors.append(
                "micro_ros_transport must be one of: serial, udp4 "
                f"(got '{micro_ros_transport}')."
            )

        if micro_ros_transport == "serial" and not _exists(micro_ros_dev):
            errors.append(
                "micro-ROS serial transport selected but device does not "
                f"exist: {micro_ros_dev}"
            )

    if use_legacy_bridges and not _exists(serial_port):
        errors.append(
            "Legacy bridge mode selected but serial port does not exist: "
            f"{serial_port}"
        )

    if (
        use_micro_ros
        and use_legacy_bridges
        and allow_mixed_bridges
        and micro_ros_transport == "serial"
        and micro_ros_dev == serial_port
    ):
        errors.append(
            "Mixed mode selected with a shared serial device for both "
            "micro-ROS and legacy bridges. Use separate devices or disable "
            "one mode."
        )

    if errors:
        raise RuntimeError("[rock64_bringup preflight] " + " | ".join(errors))

    return []
