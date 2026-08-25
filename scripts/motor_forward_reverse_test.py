#!/usr/bin/env python3
"""Guarded 1-second forward/reverse motor test for the WCH UART link.

MAINTENANCE ONLY: run with tracks raised for commissioning; normal driving
must use the ROS safety gateway and hardened bridge.

The default command uses the full normalized command range (1.0 RPS). Both
tracked motors receive the same sign. The script always sends a final stop.
It requires --confirm so it cannot be started accidentally.
"""

import argparse
import struct
import time

import serial

from motor_link_safe_test import (
    MOTOR_SET_SPEED,
    MOTOR_STOP,
    frame,
    require_wch,
)
from stm32_link import DEFAULT_BAUD, DEFAULT_PORT


def speed_frame(rps: float) -> bytes:
    return frame(
        bytes([MOTOR_SET_SPEED, 2])
        + struct.pack("<Bf", 0, rps)
        + struct.pack("<Bf", 1, rps)
    )


def send_for(link: serial.Serial, command: bytes, duration: float) -> None:
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        link.write(command)
        link.flush()
        time.sleep(0.02)  # 50 Hz; keeps the STM32 command watchdog fresh.


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD)
    parser.add_argument(
        "--rps",
        type=float,
        default=1.0,
        help="normalized motor speed (default: full command range)",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="confirm tracks are lifted and motor power is intentionally enabled",
    )
    args = parser.parse_args()

    if not args.confirm:
        raise SystemExit(
            "Refusing to move: verify tracks are lifted, then rerun with --confirm"
        )
    if not 0.01 <= args.rps <= 1.0:
        raise SystemExit("--rps must be between 0.01 and 1.0")

    require_wch(args.port)
    stop = frame(bytes([MOTOR_STOP, 0]))
    forward = speed_frame(args.rps)
    reverse = speed_frame(-args.rps)

    with serial.Serial(args.port, args.baud, timeout=0.2, write_timeout=0.2) as link:
        link.write(stop)
        link.flush()
        time.sleep(0.1)
        try:
            print(f"forward {args.rps:.3f} for 1.0 s")
            send_for(link, forward, 1.0)
            print(f"reverse {-args.rps:.3f} for 1.0 s")
            send_for(link, reverse, 1.0)
        finally:
            link.write(stop)
            link.flush()
            print("stop sent")


if __name__ == "__main__":
    main()
