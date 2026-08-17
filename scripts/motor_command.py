#!/usr/bin/env python3
"""Send one bounded direct motor command over the Rock64 WCH link."""

from __future__ import annotations

import argparse
import struct
import time

import serial

from motor_link_safe_test import MOTOR_SET_SPEED, MOTOR_STOP, frame
from stm32_link import DEFAULT_BAUD, DEFAULT_PORT, require_wch


def speed_frame(rps: float) -> bytes:
    payload = bytes([MOTOR_SET_SPEED, 2])
    payload += struct.pack("<Bf", 0, rps)
    payload += struct.pack("<Bf", 1, rps)
    return frame(payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("direction", choices=("forward", "back", "stop"))
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD)
    parser.add_argument("--seconds", type=float, default=1.0)
    parser.add_argument("--rps", type=float, default=0.10)
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()

    if args.seconds <= 0.0:
        raise SystemExit("--seconds must be positive")
    if not 0.01 <= args.rps <= 1.0:
        raise SystemExit("--rps must be between 0.01 and 1.0")
    if args.direction != "stop" and not args.confirm:
        raise SystemExit("refusing nonzero command without --confirm")

    require_wch(args.port)
    stop = frame(bytes([MOTOR_STOP, 0]))
    sign = 1.0 if args.direction == "forward" else -1.0
    command = stop if args.direction == "stop" else speed_frame(sign * args.rps)

    with serial.Serial(args.port, args.baud, timeout=0.2, write_timeout=0.2) as link:
        link.write(stop)
        link.flush()
        if args.direction != "stop":
            deadline = time.monotonic() + args.seconds
            while time.monotonic() < deadline:
                link.write(command)
                link.flush()
                time.sleep(0.02)
        link.write(stop)
        link.flush()

    print(f"{args.direction}: command sent; final stop sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
