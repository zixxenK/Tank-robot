#!/usr/bin/env python3
"""Start the flashed STM32 application from the ROM serial bootloader.

This sends only the STM32 bootloader sync and GO command. The application
itself starts with its emergency stop active; no motor command is sent here.
"""

from __future__ import annotations

import argparse

import serial

from stm32_link import DEFAULT_PORT, WCH_UART, WCH_PINS, require_wch


ACK = 0x79


def exchange(port: serial.Serial, data: bytes) -> None:
    port.write(data)
    port.flush()
    response = port.read(1)
    if response != bytes([ACK]):
        raise RuntimeError(f"STM32 bootloader expected ACK, got {response.hex()}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default=DEFAULT_PORT)
    args = parser.parse_args()
    require_wch(args.port)

    port = None
    for baud in (115200, 57600, 38400, 9600, 1000000):
        for parity in (serial.PARITY_EVEN, serial.PARITY_NONE):
            candidate = serial.Serial(
                args.port,
                baud,
                bytesize=serial.EIGHTBITS,
                parity=parity,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.4,
                write_timeout=1.0,
            )
            candidate.reset_input_buffer()
            candidate.write(bytes([0x7F]))
            candidate.flush()
            if candidate.read(1) == bytes([ACK]):
                port = candidate
                print(f"STM32 bootloader sync: {baud} baud, parity={parity}")
                break
            candidate.close()
        if port is not None:
            break

    if port is None:
        raise RuntimeError(
            f"STM32 ROM bootloader did not answer on {WCH_UART} {WCH_PINS}"
        )

    with port:

        # GET command is not needed; GO is 0x21 followed by its XOR checksum.
        exchange(port, bytes([0x21, 0xDE]))

        address = bytes([0x08, 0x00, 0x00, 0x00])
        exchange(port, address + bytes([address[0] ^ address[1] ^ address[2] ^ address[3]]))

    print("STM32 bootloader started application at 0x08000000")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
