#!/usr/bin/env bash
# Install udev rules for the Rock64 Ranger STM32 serial port.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

sudo cp "${SCRIPT_DIR}"/*.rules /etc/udev/rules.d/
echo "[udev] Rules installed to /etc/udev/rules.d/"

echo "[udev] Reloading udev rules..."
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=tty
echo "[udev] Done. Reconnect the USB cable if the device was already plugged in."
echo "[udev] Verify: ls -l /dev/rock64_stm32"
