#!/usr/bin/env python3
"""Backward-compatible wrapper for the renamed STM32 serial bridge."""

from robot_drivers.stm32_serial_bridge import STM32SerialBridge, main

__all__ = ["STM32SerialBridge", "main"]
