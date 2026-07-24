#!/usr/bin/env python3
"""One-shot PS5 joystick device readiness check.

Checks whether the configured Linux joystick device exists and is readable.
Exits 0 on success, 1 on failure.
"""

import argparse
import os


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--joy-device", default="/dev/input/js0")
    args = parser.parse_args()

    device = args.joy_device

    if not os.path.exists(device):
        print(f"PS5 CHECK FAIL: device not found: {device}")
        raise SystemExit(1)

    try:
        with open(device, "rb", buffering=0):
            pass
    except OSError as exc:
        print(f"PS5 CHECK FAIL: cannot open {device}: {exc}")
        raise SystemExit(1) from exc

    print(f"PS5 CHECK PASS: {device} is readable")
    raise SystemExit(0)


if __name__ == "__main__":
    main()
