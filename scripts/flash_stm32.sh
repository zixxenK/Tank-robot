#!/usr/bin/env bash
# flash_stm32.sh — Flash STM32F407VGTx using ST-Link
# Uses OpenOCD with verification when available; st-flash is the fallback.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
FIRMWARE_DIR="${REPO_ROOT}/firmware/stm32_chassis"
BUILD_DIR="${FIRMWARE_DIR}/build/Release"
BIN_FILE="${BUILD_DIR}/RosRobotControllerM4.bin"

DO_BUILD=false
DO_VERIFY=false
DO_ERASE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --build) DO_BUILD=true; shift ;;
    --verify) DO_VERIFY=true; shift ;;
    --erase) DO_ERASE=true; shift ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--build] [--verify] [--erase]"
      exit 1
      ;;
  esac
done

if [[ "${DO_BUILD}" == true ]]; then
  echo "[flash] Building firmware..."
  cd "${FIRMWARE_DIR}"
  rm -rf build/Release
  cmake -S . -B build/Release -DCMAKE_BUILD_TYPE=Release -DCMAKE_TOOLCHAIN_FILE=cmake/gcc-arm-none-eabi.cmake -G 'Unix Makefiles'
  cmake --build build/Release -j4
fi

if [[ ! -f "${BIN_FILE}" ]]; then
  echo "[flash] ERROR: Firmware not found at ${BIN_FILE}"
  echo "[flash] Run with --build to generate it first"
  exit 1
fi

echo "[flash] Flashing ${BIN_FILE} via ST-Link..."

if command -v openocd >/dev/null 2>&1; then
  echo "[flash] Using OpenOCD..."
  # Rock64 OpenOCD 0.11 uses hla_swd. Override this for a newer desktop
  # build with: OPENOCD_TRANSPORT=swd ./scripts/flash_stm32.sh ...
  OPENOCD_TRANSPORT="${OPENOCD_TRANSPORT:-hla_swd}"
  PROGRAM_CMD="program \"${BIN_FILE}\" 0x08000000"
  if [[ "${DO_VERIFY}" == true ]]; then
    PROGRAM_CMD+=" verify"
  fi
  PROGRAM_CMD+=" reset shutdown"

  OPENOCD_CMD="transport select ${OPENOCD_TRANSPORT}; init"
  if [[ "${DO_ERASE}" == true ]]; then
    OPENOCD_CMD+="; stm32f4x mass_erase 0"
  fi
  OPENOCD_CMD+="; ${PROGRAM_CMD}"

  openocd -f "${SCRIPT_DIR}/openocd_stm32f407.cfg" -c "${OPENOCD_CMD}"
elif command -v st-flash >/dev/null 2>&1; then
  echo "[flash] OpenOCD not found; using st-flash fallback..."
  st-flash --reset write "${BIN_FILE}" 0x08000000
else
  echo "[flash] ERROR: neither openocd nor st-flash is available"
  exit 1
fi

echo "[flash] Flash complete"
