#!/usr/bin/env bash
# flash_esp32.sh — Flash ESP32-S3 camera via USB-C using esptool
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
FIRMWARE_DIR="${REPO_ROOT}/firmware/esp32_sensors"
BUILD_DIR="${FIRMWARE_DIR}/.pio/build/esp32cam"
FIRMWARE_BIN="${BUILD_DIR}/firmware.bin"

DO_BUILD=false
USB_PORT="${ESP32_PORT:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --build) DO_BUILD=true; shift ;;
    --port) USB_PORT="${2:-}"; shift 2 ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--build] [--port /dev/ttyUSBx]"
      exit 1
      ;;
  esac
done

# Check for esptool in local bin or system path
ESPTOOL=""
if [[ -x "$HOME/.local/bin/esptool" ]]; then
  ESPTOOL="$HOME/.local/bin/esptool"
elif command -v esptool >/dev/null 2>&1; then
  ESPTOOL="esptool"
else
  echo "[flash] ERROR: esptool not found in PATH"
  echo "[flash] Install it with: python3 -m pip install esptool --user"
  exit 1
fi

if [[ "${DO_BUILD}" == true ]]; then
  echo "[flash] Building firmware..."
  cd "${FIRMWARE_DIR}"
  
  # Check for platformio
  PIO=""
  if [[ -x "$HOME/.local/bin/pio" ]]; then
    PIO="$HOME/.local/bin/pio"
  elif command -v pio >/dev/null 2>&1; then
    PIO="pio"
  else
    echo "[flash] ERROR: platformio not found in PATH"
    echo "[flash] Install it with: python3 -m pip install platformio --user"
    exit 1
  fi
  
  ${PIO} run
fi

if [[ ! -f "${FIRMWARE_BIN}" ]]; then
  echo "[flash] ERROR: Firmware not found at ${FIRMWARE_BIN}"
  echo "[flash] Run with --build to generate it first"
  exit 1
fi

echo "[flash] Flashing ${FIRMWARE_BIN} via USB-C..."

if [[ -z "${USB_PORT}" ]]; then
  echo "[flash] ERROR: ESP32_PORT is not set"
  echo "[flash] Pass --port /dev/ttyUSBx (or set ESP32_PORT)."
  exit 1
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

# Flash the firmware
${ESPTOOL} --chip esp32s3 --port "${USB_PORT}" --baud 921600 write-flash 0x0 "${FIRMWARE_BIN}"

echo "[flash] Flash complete"
