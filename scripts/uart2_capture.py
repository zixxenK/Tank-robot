#!/usr/bin/env python3
"""Capture raw bytes from the STM32 UART1/USART1 WCH link for diagnosis only.

The filename is retained for compatibility with earlier commands; UART2 is
not the Hiwonder board's WCH motor transport.
"""

from __future__ import annotations

import argparse
import time

import serial

from stm32_link import DEFAULT_BAUD, DEFAULT_PORT, require_wch


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD)
    parser.add_argument("--seconds", type=float, default=2.0)
    args = parser.parse_args()
    require_wch(args.port)
    with serial.Serial(args.port, args.baud, timeout=0.1) as port:
        end = time.monotonic() + args.seconds
        data = bytearray()
        while time.monotonic() < end:
            data.extend(port.read(256))
    print(data.hex())
    print(f"bytes={len(data)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
