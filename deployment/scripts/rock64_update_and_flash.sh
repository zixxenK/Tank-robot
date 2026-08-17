#!/usr/bin/env bash
# Build the canonical Rock64 host stack and STM32 image, then flash the STM32
# through the ST-Link connected to this Rock64.  This is intentionally an
# explicit operator action; the periodic self-update service never calls it.
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
HOST_WS="${REPO_ROOT}/host_ws"
BACKUP_ROOT="${REPO_ROOT}/.codex-backups"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="${BACKUP_ROOT}/${STAMP}"
SERVICE="rock64-robot.service"
SERVICE_WAS_ACTIVE=false

die() {
  echo "[rock64_update] ERROR: $*" >&2
  exit 1
}

as_root() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

restore_service() {
  if [[ "${SERVICE_WAS_ACTIVE}" == true ]]; then
    echo "[rock64_update] Restarting ${SERVICE}..."
    as_root systemctl restart "${SERVICE}" || true
  fi
}

trap restore_service EXIT

[[ "$(uname -m)" == "aarch64" ]] || die "run this script on the Rock64 (aarch64), not a development PC"
[[ -d "${REPO_ROOT}/.git" ]] || die "repository root is not a Git checkout: ${REPO_ROOT}"
[[ -d "${HOST_WS}/src" ]] || die "ROS workspace is missing: ${HOST_WS}/src"
[[ -x "${REPO_ROOT}/scripts/flash_stm32.sh" || -f "${REPO_ROOT}/scripts/flash_stm32.sh" ]] || die "STM32 flash script is missing"

command -v cmake >/dev/null 2>&1 || die "cmake is not installed"
command -v colcon >/dev/null 2>&1 || die "colcon is not installed"
command -v arm-none-eabi-gcc >/dev/null 2>&1 || die "ARM GNU toolchain is not installed"
command -v python3 >/dev/null 2>&1 || die "python3 is not installed"
python3 -c 'import serial' >/dev/null 2>&1 || die "python3-serial is not installed"
command -v st-flash >/dev/null 2>&1 || command -v openocd >/dev/null 2>&1 || die "neither st-flash nor openocd is installed"
command -v openocd >/dev/null 2>&1 || die "openocd is required to start the image with NRST disconnected"

echo "[rock64_update] Production host link: UART1 / USART1 / PA9-PA10"

[[ -e /dev/rock64_stm32 ]] || die "/dev/rock64_stm32 is missing"
lsusb | grep -q '1a86:55d4' || die "WCH motor UART 1a86:55d4 is not connected"
lsusb | grep -q '0483:3748' || die "ST-Link 0483:3748 is not connected"
st-info --probe >/dev/null || die "ST-Link probe failed"

if systemctl is-active --quiet "${SERVICE}"; then
  SERVICE_WAS_ACTIVE=true
fi

echo "[rock64_update] Repository: ${REPO_ROOT}"
echo "[rock64_update] Backup: ${BACKUP_DIR}"
mkdir -p "${BACKUP_DIR}"
tar --exclude='firmware/stm32_chassis/build' \
    --exclude='host_ws/build' --exclude='host_ws/install' --exclude='host_ws/log' \
    --exclude='*.bin' --exclude='*.elf' --exclude='*.hex' --exclude='*.map' \
    -czf "${BACKUP_DIR}/source.tgz" -C "${REPO_ROOT}" \
    deployment scripts host_ws/src firmware/stm32_chassis Makefile

echo "[rock64_update] Installing host dependencies..."
# shellcheck source=/dev/null
set +u
source /opt/ros/humble/setup.bash
set -u
cd "${HOST_WS}"
rosdep install --from-paths src --ignore-src -r -y

echo "[rock64_update] Building ROS packages..."
colcon build --symlink-install \
  --packages-up-to agent_core robot_bringup robot_drivers robot_teleop

echo "[rock64_update] Building STM32 Release image..."
export STM32_BUILD_JOBS="${STM32_BUILD_JOBS:-4}"
bash "${REPO_ROOT}/scripts/flash_stm32.sh" --build

echo "[rock64_update] Stopping ${SERVICE} before programming..."
if [[ "${SERVICE_WAS_ACTIVE}" == true ]]; then
  as_root systemctl stop "${SERVICE}"
fi

echo "[rock64_update] Flashing and verifying STM32 through Rock64 ST-Link..."
bash "${REPO_ROOT}/scripts/flash_stm32.sh" --verify

echo "[rock64_update] Starting the flashed application through SWD..."
bash "${REPO_ROOT}/scripts/stm32_start_app.sh"

echo "[rock64_update] Running safe UART proof (stop + zero-speed only)..."
sleep 1
cd "${REPO_ROOT}"
python3 scripts/motor_link_safe_test.py --port /dev/rock64_stm32
echo "[rock64_update] Safe UART proof passed."

IMAGE="${REPO_ROOT}/firmware/stm32_chassis/build/Release/RosRobotControllerM4.bin"
echo "[rock64_update] Firmware SHA-256: $(sha256sum "${IMAGE}" | awk '{print $1}')"
echo "[rock64_update] Flash and verification completed."
echo "[rock64_update] Firmware is running and the safe UART proof passed."

# Re-source the newly generated overlay before service restart. The service
# itself sources it independently, but this makes the health check below use
# exactly the same environment.
set +u
source "${HOST_WS}/install/setup.bash"
set -u
restore_service
SERVICE_WAS_ACTIVE=false
trap - EXIT

if systemctl is-active --quiet "${SERVICE}"; then
  echo "[rock64_update] ${SERVICE} is active."
elif [[ "${SERVICE_WAS_ACTIVE}" == false ]]; then
  echo "[rock64_update] ${SERVICE} was inactive before deployment; leaving it stopped."
else
  die "${SERVICE} did not become active after the update"
fi

echo "[rock64_update] Update complete. Backup retained at ${BACKUP_DIR}."
