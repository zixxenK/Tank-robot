#!/usr/bin/env python3
"""One-shot PS5 joystick device readiness check and interactive monitor.

Checks whether the configured Linux joystick device exists and is readable.
With --monitor, provides a live real-time visual inspection of sticks and triggers.
"""

import argparse
import os
import select
import struct
import sys
import time
from pathlib import Path

from robot_control.control_map import (
    default_control_map,
    load_control_map,
    trigger_pressure,
)
from robot_teleop.ps5_ros_bridge import detect_device_profile, find_joystick_device


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser used by the readiness check."""
    parser = argparse.ArgumentParser(
        description="PS5 DualSense device readiness check and live monitor."
    )
    parser.add_argument(
        "--joy-device",
        "--device",
        dest="joy_device",
        default="auto",
        help="Linux joystick device or 'auto' for auto-detection (default: auto)",
    )
    parser.add_argument(
        "--control-map-path",
        default="",
        help="Canonical control-map YAML (default: workspace/package map)",
    )
    parser.add_argument(
        "--monitor",
        "-m",
        action="store_true",
        help="Run interactive real-time monitor to view sticks, triggers, and buttons",
    )
    return parser


def _load_control_map(configured_path: str):
    """Resolve the canonical map for the standalone monitor."""
    candidates = []
    if configured_path:
        candidates.append(Path(configured_path))
    candidates.append(
        Path(__file__).resolve().parents[2]
        / "robot_control"
        / "config"
        / "control_map.yaml"
    )
    for candidate in candidates:
        if candidate.is_file():
            try:
                return load_control_map(candidate)
            except (OSError, ValueError, ImportError):
                pass
    return default_control_map()


def run_monitor(device: str, control_map_path: str = "") -> None:
    control_map = _load_control_map(control_map_path)
    profile_name = detect_device_profile(device)
    profile = control_map.profile(profile_name)
    print(f"Opening {device} in monitor mode (Detected layout: {profile_name})...")
    print("Move sticks / press buttons to view inputs. Press Ctrl+C to exit.\n")

    axes = [0.0] * 16
    buttons = [0] * 32

    try:
        with open(device, "rb", buffering=0) as fd:
            while True:
                r, _, _ = select.select([fd], [], [], 0.05)
                if r:
                    data = fd.read(8)
                    if data and len(data) == 8:
                        _, value, ev_type, number = struct.unpack("IhBB", data)
                        clean_type = ev_type & ~0x80
                        if clean_type == 0x02 and number < len(axes):
                            axes[number] = value / 32767.0
                        elif clean_type == 0x01 and number < len(buttons):
                            buttons[number] = 1 if value else 0

                # Print formatted status line
                throttle_axis = profile["throttle_axis"]
                steer_axis = profile["steer_axis"]
                drift_axis = profile["drift_axis"]
                multiplier_axis = profile["multiplier_axis"]
                ls_y = -axes[throttle_axis]  # Up is positive
                rs_x = axes[steer_axis]  # Positive is operator right
                l2_press = trigger_pressure(
                    axes[drift_axis], control_map.trigger_deadzone
                )
                r2_press = trigger_pressure(
                    axes[multiplier_axis], control_map.trigger_deadzone
                )

                active_btns = [str(i) for i, b in enumerate(buttons) if b]
                btns_str = ",".join(active_btns) if active_btns else "none"

                line = (
                    f"\r[PS5 Monitor] Throttle (LS Y): {ls_y:+0.2f} | "
                    f"Steer (RS X): {rs_x:+0.2f} | "
                    f"L2 Drift: {l2_press*100:3.0f}% | "
                    f"R2 Throttle: {r2_press*100:3.0f}% | "
                    f"Btns: {btns_str:<10}"
                )
                sys.stdout.write(line)
                sys.stdout.flush()
                time.sleep(0.02)
    except KeyboardInterrupt:
        print("\nExiting monitor.")


def main() -> None:
    args = build_parser().parse_args()
    req_device = args.joy_device

    resolved_device = find_joystick_device(req_device)
    if not resolved_device:
        print(f"PS5 CHECK FAIL: no joystick device found (requested: {req_device})")
        raise SystemExit(1)

    try:
        with open(resolved_device, "rb", buffering=0):
            pass
    except OSError as exc:
        print(f"PS5 CHECK FAIL: cannot open {resolved_device}: {exc}")
        raise SystemExit(1) from exc

    profile_name = detect_device_profile(resolved_device)
    print(f"PS5 CHECK PASS: {resolved_device} is readable (Profile: {profile_name})")

    if args.monitor:
        run_monitor(resolved_device, args.control_map_path)

    raise SystemExit(0)


if __name__ == "__main__":
    main()
