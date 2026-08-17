#!/usr/bin/env python3
"""Canonical hardware facts for the Hiwonder ROS Robot Controller V1.2.

The board's WCH USB-UART device is the Rock64 motor transport.  The physical
connector is product-labeled UART1 and is connected to USART1 on PA9/PA10.
ST-Link is a separate SWD programmer and is never a motor-data port.
"""

from __future__ import annotations

import os

from serial.tools import list_ports


DEFAULT_PORT = "/dev/rock64_stm32"
DEFAULT_BAUD = 1_000_000
WCH_VID = 0x1A86
WCH_PID = 0x55D4
WCH_UART = "UART1 / USART1"
WCH_PINS = "PA9/PA10"
STLINK_VID = 0x0483
STLINK_PID = 0x3748
NATIVE_USB_VID = 0x0483
NATIVE_USB_PID = 0x5740


def require_wch(port: str = DEFAULT_PORT) -> None:
    """Refuse to use ST-Link, native USB, or an unrelated serial adapter."""

    requested = os.path.realpath(port)
    for info in list_ports.comports():
        if info.device != port and os.path.realpath(info.device) != requested:
            continue
        if info.vid != WCH_VID or info.pid != WCH_PID:
            raise SystemExit(
                f"Refusing {port}: expected Hiwonder WCH USB-UART "
                f"{WCH_VID:04x}:{WCH_PID:04x} for {WCH_UART} {WCH_PINS}; "
                f"found {info.vid!s}:{info.pid!s}"
            )
        return
    raise SystemExit(f"WCH motor port is not present: {port}")
