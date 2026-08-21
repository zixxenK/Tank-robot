#!/usr/bin/env bash
# Start the image at 0x08000000 through SWD when BOOT0 selects the STM32 system
# bootloader and the board's NRST wire is not available. Reset first so the
# application gets clean RCC/peripheral state, then vector the halted core to
# the user image explicitly. This does not write flash or send motion.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPENOCD_TRANSPORT="${OPENOCD_TRANSPORT:-hla_swd}"

command -v openocd >/dev/null 2>&1 || {
  echo "[stm32_start_app] ERROR: openocd is not installed" >&2
  exit 1
}

openocd -f "${SCRIPT_DIR}/openocd_stm32f407.cfg" \
  -c "transport select ${OPENOCD_TRANSPORT}; init; reset halt; \
      mww 0xE000ED08 0x08000000; \
      mww 0xE000ED04 0; \
      reg msp [mrw 0x08000000]; \
      reg pc [mrw 0x08000004]; \
      reg xPSR 0x01000000; reg lr 0xffffffff; \
      reg primask 0; reg faultmask 0; reg basepri 0; reg control 0; \
      resume; shutdown"
