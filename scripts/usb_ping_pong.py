#!/usr/bin/env python3
"""Exercise the optional STM32 native USB CDC diagnostic link only.

The test sends ASCII ``PING\\n`` and expects ``PONG\\n``. It does not open
or reference the WCH USB-UART adapter and it sends no robot protocol frames.
"""

from __future__ import annotations

import argparse
import sys
import time

import serial
from serial.tools import list_ports


PING = b"PING\n"
PONG = b"PONG\n"
STM32_VID = 0x0483
STM32_PID = 0x5740


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--port",
        default="/dev/rock64_stm32_usb",
        help="optional native STM32 USB CDC device (not the WCH motor link)",
    )
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=1.0)
    args = parser.parse_args()

    if args.count < 1:
        parser.error("--count must be positive")

    try:
        with serial.Serial(args.port, 115200, timeout=0.05, write_timeout=1.0) as port:
            if port.vid != STM32_VID or port.pid != STM32_PID:
                print(
                    f"REFUSING {args.port}: expected optional STM32 USB CDC "
                    f"{STM32_VID:04x}:{STM32_PID:04x}, "
                    f"found {port.vid!s}:{port.pid!s}",
                    file=sys.stderr,
                )
                return 2

            for sequence in range(1, args.count + 1):
                port.reset_input_buffer()
                port.write(PING)
                port.flush()

                received = bytearray()
                deadline = time.monotonic() + args.timeout
                while time.monotonic() < deadline and PONG not in received:
                    received.extend(port.read(32))

                if PONG not in received:
                    print(
                        f"PING {sequence}: timeout; RX={bytes(received).hex()}",
                        file=sys.stderr,
                    )
                    return 1
                print(f"PING {sequence}: PONG")
    except (OSError, serial.SerialException) as exc:
        print(
            f"cannot open optional native STM32 USB CDC {args.port}: {exc}; "
            "normal motor communication uses /dev/rock64_stm32 (WCH 1a86:55d4)",
            file=sys.stderr,
        )
        available = [
            f"{info.device} ({info.vid:04x}:{info.pid:04x})"
            for info in list_ports.comports()
            if info.device and info.vid is not None and info.pid is not None
        ]
        available.extend(
            info.device
            for info in list_ports.comports()
            if info.device and (info.vid is None or info.pid is None)
        )
        if available:
            print("available ports: " + ", ".join(available), file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
