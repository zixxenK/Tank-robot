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
        "--monitor",
        "-m",
        action="store_true",
        help="Run interactive real-time monitor to view sticks, triggers, and buttons",
    )
    return parser


def run_monitor(device: str) -> None:
    profile_name = detect_device_profile(device)
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
                ls_y = -axes[1]  # Up is positive
                if profile_name == "ps5_bluetooth":
                    rs_x = -axes[2]
                    l2_raw = axes[3]
                    r2_raw = axes[4]
                else:
                    rs_x = -axes[3]
                    l2_raw = axes[2]
                    r2_raw = axes[5]

                l2_press = max(0.0, min(1.0, (l2_raw + 1.0) / 2.0))
                r2_press = max(0.0, min(1.0, (r2_raw + 1.0) / 2.0))

                active_btns = [str(i) for i, b in enumerate(buttons) if b]
                btns_str = ",".join(active_btns) if active_btns else "none"

                line = (
                    f"\r[PS5 Monitor] Throttle (LS Y): {ls_y:+0.2f} | "
                    f"Steer (RS X): {rs_x:+0.2f} | "
                    f"L2 Brake: {l2_press*100:3.0f}% | "
                    f"R2 Brake: {r2_press*100:3.0f}% | "
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
        run_monitor(resolved_device)

    raise SystemExit(0)


if __name__ == "__main__":
    main()
