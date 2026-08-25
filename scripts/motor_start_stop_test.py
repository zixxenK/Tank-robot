#!/usr/bin/env python3
"""Guarded, independent motor 1 / motor 2 start-stop proof test.

MAINTENANCE ONLY: this is a direct WCH UART commissioning path for raised
tracks. It is not a normal operator drive interface.

The test uses the same packed frame as the ROS 2 STM32 bridge, but talks to
the WCH adapter directly so it is useful before ROS 2 is started. It always
ends with an emergency stop. Run with tracks lifted and use ``--confirm``.
"""

import argparse
import struct
import time

import serial

from motor_link_safe_test import MOTOR_SET_SPEED, MOTOR_STOP, frame, require_wch
from stm32_link import DEFAULT_BAUD, DEFAULT_PORT


def pair_frame(motor_id: int, rps: float) -> bytes:
    """Command one motor while explicitly holding the other at zero."""
    other_id = 1 if motor_id == 0 else 0
    payload = bytes([MOTOR_SET_SPEED, 2])
    payload += struct.pack("<Bf", motor_id, rps)
    payload += struct.pack("<Bf", other_id, 0.0)
    return frame(payload)


def send_for(link: serial.Serial, command: bytes, duration: float) -> None:
    """Refresh the STM32 250 ms command watchdog for the requested interval."""
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        link.write(command)
        link.flush()
        time.sleep(0.02)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD)
    parser.add_argument(
        "--rps",
        type=float,
        default=1.0,
        help="normalized motor speed (default: full command range)",
    )
    parser.add_argument("--duration", type=float, default=1.0)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the exact M1/M2 frames without opening hardware",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="confirm tracks are lifted and motor power is intentionally enabled",
    )
    args = parser.parse_args()

    if not args.dry_run and not args.confirm:
        raise SystemExit(
            "Refusing to move: lift the tracks, then rerun with --confirm"
        )
    if not 0.01 <= args.rps <= 1.0:
        raise SystemExit("--rps must be between 0.01 and 1.0")
    if args.duration <= 0.0:
        raise SystemExit("--duration must be positive")

    stop = frame(bytes([MOTOR_STOP, 0]))
    motor_1_start = pair_frame(0, args.rps)
    motor_2_start = pair_frame(1, args.rps)

    if args.dry_run:
        print(f"M1 START: {motor_1_start.hex(' ')}")
        print(f"M2 START: {motor_2_start.hex(' ')}")
        print(f"STOP:     {stop.hex(' ')}")
        return

    require_wch(args.port)
    with serial.Serial(args.port, args.baud, timeout=0.2, write_timeout=0.2) as link:
        link.write(stop)
        link.flush()
        time.sleep(0.1)
        try:
            print("M1 START")
            send_for(link, motor_1_start, args.duration)
            print("M1 STOP")
            link.write(stop)
            link.flush()
            time.sleep(0.25)

            print("M2 START")
            send_for(link, motor_2_start, args.duration)
            print("M2 STOP")
            link.write(stop)
            link.flush()
        finally:
            link.write(stop)
            link.flush()
            print("FINAL EMERGENCY STOP")


if __name__ == "__main__":
    main()
