#!/usr/bin/env bash
# flash_stm32.sh — Flash STM32F407VGTx firmware using OpenOCD
#
# Usage:
#   ./flash_stm32.sh [--build] [--verify] [--erase]
#
# Options:
#   --build   Build firmware before flashing
#   --verify  Verify flash after programming
#   --erase   Perform full chip erase before programming
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
FIRMWARE_DIR="${REPO_ROOT}/firmware/stm32_chassis"
BUILD_DIR="${FIRMWARE_DIR}/build"
ELF_FILE="${BUILD_DIR}/rock64_ranger_fw.elf"

# ── Defaults ──────────────────────────────────────────────────────────────
DO_BUILD=false
DO_VERIFY=false
DO_ERASE=false

# ── Parse command-line args ───────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --build)   DO_BUILD=true;  shift ;;
    --verify)  DO_VERIFY=true; shift ;;
    --erase)   DO_ERASE=true;  shift ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--build] [--verify] [--erase]"
      exit 1
      ;;
  esac
done

# ── Build firmware if requested ───────────────────────────────────────────
if [[ "${DO_BUILD}" == true ]]; then
  echo "[flash] Building firmware..."
  mkdir -p "${BUILD_DIR}"
  cd "${FIRMWARE_DIR}"
  cmake -B build -DCMAKE_TOOLCHAIN_FILE=cmake/stm32_toolchain.cmake
  cmake --build build
  echo "[flash] Build complete"
fi

# ── Check if ELF file exists ──────────────────────────────────────────────
if [[ ! -f "${ELF_FILE}" ]]; then
  echo "[flash] ERROR: Firmware not found at ${ELF_FILE}"
  echo "[flash] Run with --build to build firmware first"
  exit 1
fi

# ── Flash firmware using OpenOCD ───────────────────────────────────────────
echo "[flash] Flashing firmware to STM32F407VGTx..."

OPENOCD_SCRIPTS="
init
"

if [[ "${DO_ERASE}" == true ]]; then
  OPENOCD_SCRIPTS+="stm32f4x mass_erase 0
"
fi

OPENOCD_SCRIPTS+="program ${ELF_FILE} verify reset
shutdown
"

# Use OpenOCD with ST-Link interface
# Assumes ST-Link v2 or v3 is connected
echo "${OPENOCD_SCRIPTS}" | openocd -f "${SCRIPT_DIR}/openocd_stm32f407.cfg" -c commands

echo "[flash] Flash complete!"

if [[ "${DO_VERIFY}" == true ]]; then
  echo "[flash] Verification complete (verify flag was used during programming)"
fi
