#!/usr/bin/env bash
# flash_stm32.sh — Flash STM32F407VGTx using ST-Link
# Prefers st-flash tool, falls back to OpenOCD if not available
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
FIRMWARE_DIR="${REPO_ROOT}/firmware/stm32_chassis"
BUILD_DIR="${FIRMWARE_DIR}/build/Release"
ELF_FILE="${BUILD_DIR}/RosRobotControllerM4.elf"

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

if [[ ! -f "${ELF_FILE}" ]]; then
  echo "[flash] ERROR: Firmware not found at ${ELF_FILE}"
  echo "[flash] Run with --build to generate it first"
  exit 1
fi

echo "[flash] Flashing ${ELF_FILE} via ST-Link..."

# Prefer st-flash if available, it's more reliable
if command -v st-flash >/dev/null 2>&1; then
  echo "[flash] Using st-flash tool..."
  ELF_FILE="${BUILD_DIR}/RosRobotControllerM4.elf"
  if [[ ! -f "${ELF_FILE}" ]]; then
    echo "[flash] ERROR: ELF file not found at ${ELF_FILE}"
    exit 1
  fi
  st-flash --reset write "${ELF_FILE}" 0x8000000
else
  echo "[flash] st-flash not found, using OpenOCD..."
  if ! command -v openocd >/dev/null 2>&1; then
    echo "[flash] ERROR: openocd not found in PATH"
    exit 1
  fi
  
  BIN_FILE="${BUILD_DIR}/RosRobotControllerM4.bin"
  PROGRAM_CMD="program \"${BIN_FILE}\" 0x8000000"
  if [[ "${DO_VERIFY}" == true ]]; then
    PROGRAM_CMD+=" verify"
  fi
  PROGRAM_CMD+=" reset"
  
  OPENOCD_CMD="init"
  if [[ "${DO_ERASE}" == true ]]; then
    OPENOCD_CMD+="; stm32f4x mass_erase 0"
  fi
  OPENOCD_CMD+="; ${PROGRAM_CMD}; shutdown"
  
  openocd -f "${SCRIPT_DIR}/openocd_stm32f407.cfg" -c "${OPENOCD_CMD}"
fi

echo "[flash] Flash complete"
