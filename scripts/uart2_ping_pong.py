#!/usr/bin/env python3
"""Probe the Hiwonder STM32 ROM bootloader on the WCH motor cable.

The filename is retained for compatibility with the old UART2 diagnostic,
but the board's WCH connector uses the USART1 UART1 pins PA9/PA10.  The running motor
application speaks packed binary frames; it does not implement ASCII
``PING``/``PONG``.  This diagnostic therefore probes only the STM32 ROM
bootloader sync and never sends a motor frame.
"""

from __future__ import annotations

import argparse
import sys

import serial

from stm32_link import DEFAULT_PORT, WCH_UART, WCH_PINS, require_wch


ACK = b"\x79"
SYNC_BAUDS = (115200, 57600, 38400, 9600, 1_000_000)


def find_bootloader(port_name: str, timeout: float) -> serial.Serial | None:
    for baud in SYNC_BAUDS:
        for parity in (serial.PARITY_EVEN, serial.PARITY_NONE):
            port = serial.Serial(
                port_name,
                baudrate=baud,
                bytesize=serial.EIGHTBITS,
                parity=parity,
                stopbits=serial.STOPBITS_ONE,
                timeout=timeout,
                write_timeout=timeout,
            )
            port.reset_input_buffer()
            port.write(b"\x7f")
            port.flush()
            if port.read(1) == ACK:
                print(f"ROM bootloader ACK: {baud} baud, parity={parity}")
                return port
            port.close()
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--timeout", type=float, default=0.4)
    parser.add_argument(
        "--go",
        action="store_true",
        help="after sync, start the flashed application at 0x08000000",
    )
    args = parser.parse_args()

    require_wch(args.port)
    port = find_bootloader(args.port, args.timeout)
    if port is None:
        print(
            f"No ROM bootloader ACK on {WCH_UART} {WCH_PINS}. "
            "The application may already be running, or BOOT is asserted.",
            file=sys.stderr,
        )
        return 1

    with port:
        if args.go:
            port.write(b"\x21\xde")
            port.flush()
            if port.read(1) != ACK:
                print("ROM bootloader rejected GO command", file=sys.stderr)
                return 1
            address = b"\x08\x00\x00\x00"
            port.write(address + bytes([0x08]))
            port.flush()
            if port.read(1) != ACK:
                print("ROM bootloader rejected application address", file=sys.stderr)
                return 1
            print("Started application at 0x08000000; no motor command sent.")
        else:
            print("ROM bootloader is responding; no GO or motor command sent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
