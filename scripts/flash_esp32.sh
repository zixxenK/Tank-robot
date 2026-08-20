#!/usr/bin/env bash
# flash_esp32.sh — Flash ESP32-S3 camera via USB-C using platformio or esptool
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
FIRMWARE_DIR="${REPO_ROOT}/firmware/esp32_sensors"
BUILD_DIR="${FIRMWARE_DIR}/.pio/build/esp32cam"
FIRMWARE_BIN="${BUILD_DIR}/firmware.bin"
BOOTLOADER_BIN="${BUILD_DIR}/bootloader.bin"
PARTITIONS_BIN="${BUILD_DIR}/partitions.bin"

DO_BUILD=false
USB_PORT="${ESP32_PORT:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --build) DO_BUILD=true; shift ;;
    --port) USB_PORT="${2:-}"; shift 2 ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--build] [--port /dev/ttyACM1]"
      exit 1
      ;;
  esac
done

# Check for platformio
PIO=""
if [[ -x "$HOME/.local/bin/pio" ]]; then
  PIO="$HOME/.local/bin/pio"
elif command -v pio >/dev/null 2>&1; then
  PIO="pio"
fi

# Check for esptool in local bin or system path
ESPTOOL=""
if [[ -x "$HOME/.local/bin/esptool" ]]; then
  ESPTOOL="$HOME/.local/bin/esptool"
elif [[ -x "$HOME/.local/bin/esptool.py" ]]; then
  ESPTOOL="$HOME/.local/bin/esptool.py"
elif command -v esptool >/dev/null 2>&1; then
  ESPTOOL="esptool"
elif command -v esptool.py >/dev/null 2>&1; then
  ESPTOOL="esptool.py"
fi

if [[ "${DO_BUILD}" == true ]]; then
  echo "[flash] Building firmware with PlatformIO..."
  if [[ -z "${PIO}" ]]; then
    echo "[flash] ERROR: platformio not found in PATH or ~/.local/bin"
    exit 1
  fi
  cd "${FIRMWARE_DIR}"
  ${PIO} run -e esp32cam
fi

if [[ -z "${USB_PORT}" ]]; then
  # Auto-detect ESP32 /dev/ttyACM1 if available and not STM32
  if [[ -e "/dev/ttyACM1" ]]; then
    USB_PORT="/dev/ttyACM1"
  elif [[ -e "/dev/ttyUSB1" ]]; then
    USB_PORT="/dev/ttyUSB1"
  else
    echo "[flash] ERROR: ESP32_PORT is not set"
    echo "[flash] Pass --port /dev/ttyACM1 (or set ESP32_PORT)."
    exit 1
  fi
fi

if [[ "${USB_PORT}" == "/dev/rock64_stm32" ]]; then
  echo "[flash] ERROR: refusing the Hiwonder WCH motor port"
  exit 1
fi
if [[ ! -e "${USB_PORT}" ]]; then
  echo "[flash] ERROR: ESP32 port does not exist: ${USB_PORT}"
  exit 1
fi

echo "[flash] Using USB port: ${USB_PORT}"

if [[ -n "${PIO}" ]]; then
  echo "[flash] Flashing via PlatformIO upload target..."
  cd "${FIRMWARE_DIR}"
  ${PIO} run -e esp32cam -t upload --upload-port "${USB_PORT}"
elif [[ -n "${ESPTOOL}" ]]; then
  if [[ ! -f "${FIRMWARE_BIN}" || ! -f "${BOOTLOADER_BIN}" || ! -f "${PARTITIONS_BIN}" ]]; then
    echo "[flash] ERROR: Binaries not found at ${BUILD_DIR}"
    echo "[flash] Run with --build to generate them first"
    exit 1
  fi
  echo "[flash] Flashing binaries via esptool with ESP32-S3 memory layout..."
  ${ESPTOOL} --chip esp32s3 --port "${USB_PORT}" --baud 921600 write-flash \
    0x0000 "${BOOTLOADER_BIN}" \
    0x8000 "${PARTITIONS_BIN}" \
    0x10000 "${FIRMWARE_BIN}"
else
  echo "[flash] ERROR: neither platformio nor esptool is available"
  exit 1
fi

echo "[flash] Flash complete"
