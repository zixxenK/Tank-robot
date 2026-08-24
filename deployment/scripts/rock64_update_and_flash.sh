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
SYSTEMD_CONFIG="${REPO_ROOT}/deployment/systemd/systemd_config.conf"
SYSTEMD_CONFIG_EXAMPLE="${REPO_ROOT}/deployment/systemd/systemd_config.conf.example"

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

set_config_value() {
  local key="$1"
  local value="$2"

  if grep -qE "^[[:space:]]*${key}=" "${SYSTEMD_CONFIG}"; then
    sed -i -E "s|^[[:space:]]*${key}=.*$|${key}=${value}|" "${SYSTEMD_CONFIG}"
  else
    printf '\n%s=%s\n' "${key}" "${value}" >> "${SYSTEMD_CONFIG}"
  fi
}

merge_all_hardware_config() {
  if [[ ! -f "${SYSTEMD_CONFIG}" ]]; then
    [[ -f "${SYSTEMD_CONFIG_EXAMPLE}" ]] || \
      die "deployment config and example are both missing"
    cp "${SYSTEMD_CONFIG_EXAMPLE}" "${SYSTEMD_CONFIG}"
  fi

  # Preserve network, LiDAR, namespace, and other operator-specific values;
  # only enforce the peripherals required by this all-hardware release.
  set_config_value USE_HARDWARE_BRIDGE true
  set_config_value USE_TELEOP true
  set_config_value PS5_JOY_DEVICE /dev/input/ps5_controller
  set_config_value USE_CAMERA_BRIDGE true
  set_config_value USE_USB_CAMERA true
  set_config_value USB_CAMERA_DEVICE auto
  set_config_value USE_COMPRESSED_CAMERA_TRANSPORT true
  echo "[rock64_update] Enabled STM32, PS5, ESP32 camera, and USB camera in ${SYSTEMD_CONFIG}."
}

restore_service() {
  if [[ "${SERVICE_WAS_ACTIVE}" == true ]]; then
    echo "[rock64_update] Restarting ${SERVICE}..."
    if ! as_root systemctl restart "${SERVICE}"; then
      echo "[rock64_update] WARNING: failed to restart ${SERVICE} during cleanup." >&2
    fi
  fi
}

trap restore_service EXIT

[[ "$(uname -m)" == "aarch64" ]] || die "run this script on the Rock64 (aarch64), not a development PC"
[[ -d "${HOST_WS}/src" ]] || die "ROS workspace is missing: ${HOST_WS}/src"
[[ -x "${REPO_ROOT}/scripts/flash_stm32.sh" || -f "${REPO_ROOT}/scripts/flash_stm32.sh" ]] || die "STM32 flash script is missing"

command -v cmake >/dev/null 2>&1 || die "cmake is not installed"
command -v colcon >/dev/null 2>&1 || die "colcon is not installed"
command -v arm-none-eabi-gcc >/dev/null 2>&1 || die "ARM GNU toolchain is not installed"
command -v python3 >/dev/null 2>&1 || die "python3 is not installed"
python3 -c 'import serial' >/dev/null 2>&1 || die "python3-serial is not installed"
command -v st-flash >/dev/null 2>&1 || command -v openocd >/dev/null 2>&1 || die "neither st-flash nor openocd is installed"
command -v openocd >/dev/null 2>&1 || die "openocd is required to start the image with NRST disconnected"

# Authenticate before changing service state.  This keeps the EXIT trap able
# to restore an active service if the operator interrupts the build or flash.
if [[ "$(id -u)" -ne 0 ]]; then
  sudo -v
fi

merge_all_hardware_config

echo "[rock64_update] Production host link: UART1 / USART1 / PA9-PA10"

[[ -e /dev/rock64_stm32 ]] || die "/dev/rock64_stm32 is missing"
lsusb | grep -q '1a86:55d4' || die "WCH motor UART 1a86:55d4 is not connected"
lsusb | grep -q '0483:3748' || die "ST-Link 0483:3748 is not connected"
st-info --probe >/dev/null || die "ST-Link probe failed"

if systemctl is-active --quiet "${SERVICE}"; then
  SERVICE_WAS_ACTIVE=true
  echo "[rock64_update] Stopping ${SERVICE} before cleaning/building..."
  as_root systemctl stop "${SERVICE}"
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
# Do not let an older overlay (for example /home/rock64/install) influence
# dependency discovery or the generated entry-point wrappers.
unset AMENT_PREFIX_PATH CMAKE_PREFIX_PATH COLCON_PREFIX_PATH PYTHONPATH ROS_PACKAGE_PATH
# shellcheck source=/dev/null
set +u
source /opt/ros/humble/setup.bash
set -u
cd "${HOST_WS}"
rosdep install --from-paths src --ignore-src -r -y

echo "[rock64_update] Removing generated ROS state before rebuilding..."
rm -rf build install log

if [[ -d "${REPO_ROOT}/deployment/udev" ]]; then
  echo "[rock64_update] Syncing udev rules..."
  as_root cp "${REPO_ROOT}/deployment/udev/"*.rules /etc/udev/rules.d/ 2>/dev/null || true
  as_root udevadm control --reload-rules || true
  as_root udevadm trigger || true
fi

echo "[rock64_update] Building ROS packages..."
colcon build --symlink-install \
  --packages-up-to agent_core robot_bringup robot_drivers robot_teleop robot_audio \
  navigation perception telemetry_logger terrain_adaptation

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

if [[ "${SERVICE_WAS_ACTIVE}" == true ]]; then
  echo "[rock64_update] Restarting ${SERVICE} on the rebuilt workspace..."
  if ! as_root systemctl restart "${SERVICE}"; then
    die "${SERVICE} failed to restart after the update"
  fi
  if ! systemctl is-active --quiet "${SERVICE}"; then
    die "${SERVICE} did not become active after the update"
  fi
  echo "[rock64_update] ${SERVICE} is active."
else
  echo "[rock64_update] ${SERVICE} was inactive before deployment; leaving it stopped."
fi

SERVICE_WAS_ACTIVE=false
trap - EXIT
echo "[rock64_update] Update complete. Backup retained at ${BACKUP_DIR}."
