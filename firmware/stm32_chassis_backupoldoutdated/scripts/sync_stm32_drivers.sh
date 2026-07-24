#!/usr/bin/env bash
set -euo pipefail

# Sync STM32 Drivers/ from official ST repositories only.
# - HAL driver: pinned commit from stm32f4xx-hal-driver
# - CMSIS device/core: STM32CubeF4 Drivers/CMSIS

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
STM32_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
DRIVERS_DIR="${STM32_ROOT}/Drivers"
WORK_DIR="${STM32_ROOT}/.cache/stm32-drivers-sync"

HAL_REPO_URL="https://github.com/STMicroelectronics/stm32f4xx-hal-driver.git"
HAL_COMMIT="1f6451c3e07728b4c830744de380e56bf5bc0026"
CUBE_REPO_URL="https://github.com/STMicroelectronics/STM32CubeF4.git"

mkdir -p "${WORK_DIR}"
rm -rf "${WORK_DIR}/hal" "${WORK_DIR}/cube"

echo "[1/4] Fetching HAL driver @ ${HAL_COMMIT}"
git clone --filter=blob:none "${HAL_REPO_URL}" "${WORK_DIR}/hal"
(
  cd "${WORK_DIR}/hal"
  git checkout "${HAL_COMMIT}"
)

echo "[2/4] Fetching STM32CubeF4 Drivers/CMSIS"
git clone --filter=blob:none --sparse "${CUBE_REPO_URL}" "${WORK_DIR}/cube"
(
  cd "${WORK_DIR}/cube"
  git sparse-checkout set Drivers/CMSIS
)

echo "[3/4] Replacing local Drivers/"
rm -rf "${DRIVERS_DIR}"
mkdir -p "${DRIVERS_DIR}"
cp -a "${WORK_DIR}/hal" "${DRIVERS_DIR}/STM32F4xx_HAL_Driver"
rm -rf "${DRIVERS_DIR}/STM32F4xx_HAL_Driver/.git"
cp -a "${WORK_DIR}/cube/Drivers/CMSIS" "${DRIVERS_DIR}/CMSIS"

echo "[4/4] Done"
echo "Drivers synced in: ${DRIVERS_DIR}"
