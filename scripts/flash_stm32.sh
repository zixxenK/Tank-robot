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
  ROCK64_HOST_USART="${ROCK64_HOST_USART:-1}"
  case "${ROCK64_HOST_USART}" in
    1|3) ;;
    *) echo "[flash] ERROR: ROCK64_HOST_USART must be 1 or 3" >&2; exit 1 ;;
  esac
  cmake -S . -B build/Release \
    -DCMAKE_BUILD_TYPE=Release \
    -DROCK64_HOST_USART="${ROCK64_HOST_USART}" \
    -DCMAKE_TOOLCHAIN_FILE=cmake/gcc-arm-none-eabi.cmake -G 'Unix Makefiles'
  cmake --build build/Release -j"${STM32_BUILD_JOBS:-4}"
fi

if [[ ! -f "${BIN_FILE}" ]]; then
  echo "[flash] ERROR: Firmware not found at ${BIN_FILE}"
  echo "[flash] Run with --build to generate it first"
  exit 1
fi

echo "[flash] Flashing ${BIN_FILE} via ST-Link..."

if command -v st-flash >/dev/null 2>&1; then
  echo "[flash] Using st-flash (write operation self-verifies; NRST is optional)..."
  FLASH_LOG="$(mktemp)"
  set +e
  st-flash write "${BIN_FILE}" 0x08000000 >"${FLASH_LOG}" 2>&1
  FLASH_RC=$?
  set -e
  cat "${FLASH_LOG}"
  FLASH_VERIFIED=false
  if grep -q "Flash written and verified" "${FLASH_LOG}"; then
    FLASH_VERIFIED=true
  fi
  rm -f "${FLASH_LOG}"
  # st-flash 1.7 returns 1 on this board because NRST is not wired even
  # after reporting a complete write and verification.  Accept only that
  # explicit verification message; all other failures remain fatal.
  if [[ "${FLASH_RC}" -ne 0 ]]; then
    if [[ "${FLASH_VERIFIED}" != true ]]; then
      echo "[flash] ERROR: st-flash failed with status ${FLASH_RC}" >&2
      exit "${FLASH_RC}"
    fi
  fi

  if [[ "${DO_VERIFY}" == true ]]; then
    VERIFY_FILE="$(mktemp)"
    VERIFY_SIZE="$(stat -c '%s' "${BIN_FILE}")"
    echo "[flash] Reading back ${VERIFY_SIZE} bytes for verification..."
    set +e
    st-flash read "${VERIFY_FILE}" 0x08000000 "${VERIFY_SIZE}"
    READ_RC=$?
    set -e
    if [[ "${READ_RC}" -ne 0 ]]; then
      rm -f "${VERIFY_FILE}"
      echo "[flash] ERROR: st-flash readback failed with status ${READ_RC}" >&2
      exit "${READ_RC}"
    fi
    if ! cmp -s "${BIN_FILE}" "${VERIFY_FILE}"; then
      echo "[flash] ERROR: STM32 readback does not match ${BIN_FILE}" >&2
      rm -f "${VERIFY_FILE}"
      exit 1
    fi
    rm -f "${VERIFY_FILE}"
    echo "[flash] Readback verified."
  fi
elif command -v openocd >/dev/null 2>&1; then
  echo "[flash] Using OpenOCD..."
  # Rock64 OpenOCD 0.11 uses hla_swd. Override this for a newer desktop
  # build with: OPENOCD_TRANSPORT=swd ./scripts/flash_stm32.sh ...
  OPENOCD_TRANSPORT="${OPENOCD_TRANSPORT:-hla_swd}"
  # This board has a physical RST button but no connected NRST wire.  The
  # OpenOCD `program ... reset` helper therefore fails while trying to drive
  # an unavailable reset line.  Attach, halt, write, and verify explicitly;
  # the operator may press the board RST button before or after this command.
  OPENOCD_CMD="transport select ${OPENOCD_TRANSPORT}; init; halt"
  if [[ "${DO_ERASE}" == true ]]; then
    OPENOCD_CMD+="; stm32f4x mass_erase 0"
  fi
  OPENOCD_CMD+="; flash write_image erase \"${BIN_FILE}\" 0x08000000"
  if [[ "${DO_VERIFY}" == true ]]; then
    OPENOCD_CMD+="; verify_image \"${BIN_FILE}\" 0x08000000"
  fi
  OPENOCD_CMD+="; shutdown"

  openocd -f "${SCRIPT_DIR}/openocd_stm32f407.cfg" -c "${OPENOCD_CMD}"
else
  echo "[flash] ERROR: neither openocd nor st-flash is available"
  exit 1
fi

echo "[flash] Flash complete"
