#!/usr/bin/env bash
# robot_start.sh — Main ROS2 launch orchestrator for Rock64 Ranger.
#
# Called by systemd rock64-robot.service after network-online.target.
# Validates the environment, sources the ROS2 workspace, then launches
# the hardware bringup.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${DEPLOY_DIR}/.." && pwd)"

resolve_host_ws() {
  if [[ -n "${HOST_WS_PATH:-}" ]]; then
    if [[ -d "${HOST_WS_PATH}/src" ]]; then
      echo "${HOST_WS_PATH}"
      return
    else
      echo "ERROR: HOST_WS_PATH=${HOST_WS_PATH} does not contain src directory"
      exit 1
    fi
  fi

  if [[ -d "${REPO_ROOT}/host_ws/src" ]]; then
    echo "${REPO_ROOT}/host_ws"
    return
  fi

  echo "ERROR: host_ws/src not found at ${REPO_ROOT}/host_ws/src"
  echo "ERROR: Cannot proceed without valid ROS2 workspace"
  echo "Please ensure host_ws is properly checked out or set HOST_WS_PATH"
  exit 1
}

# ── Load deployment configuration ─────────────────────────────────────────
CONFIG_FILE="${DEPLOY_DIR}/systemd/systemd_config.conf"
if [[ -f "${CONFIG_FILE}" ]]; then
  # shellcheck source=/dev/null
  source "${CONFIG_FILE}"
fi

# The service must use the workspace beside this launcher. An inherited
# HOST_WS_PATH from an older checkout can otherwise start a second, stale ROS
# graph and stale serial bridge.
export HOST_WS_PATH="${REPO_ROOT}/host_ws"

# ── Environment detection & validation ────────────────────────────────────
echo "[robot_start] Rock64 Ranger starting..."
echo "[robot_start] Hostname : $(hostname)"
echo "[robot_start] Date     : $(date)"
echo "[robot_start] Repo root: ${REPO_ROOT}"
echo "[robot_start] Host WS  : $(resolve_host_ws)"

# Validate serial port
SERIAL_PORT="${SERIAL_PORT:-/dev/rock64_stm32}"
USE_HARDWARE_BRIDGE="${USE_HARDWARE_BRIDGE:-true}"
USE_TELEOP="${USE_TELEOP:-true}"
MONITOR_BATTERY="${MONITOR_BATTERY:-false}"
USE_AUDIO="${USE_AUDIO:-true}"
USE_LIDAR="${USE_LIDAR:-false}"
LIDAR_SERIAL_PORT="${LIDAR_SERIAL_PORT:-/dev/ttyS2}"
LIDAR_SYNC_GPIOCHIP="${LIDAR_SYNC_GPIOCHIP:-/dev/gpiochip2}"
USE_USB_CAMERA="${USE_USB_CAMERA:-false}"
USB_CAMERA_DEVICE="${USB_CAMERA_DEVICE:-/dev/video0}"
USE_COMPRESSED_CAMERA_TRANSPORT="${USE_COMPRESSED_CAMERA_TRANSPORT:-false}"
CAMERA_JPEG_QUALITY="${CAMERA_JPEG_QUALITY:-70}"
if [[ "${USE_HARDWARE_BRIDGE}" == "true" && ! -e "${SERIAL_PORT}" ]]; then
  echo "[robot_start] ERROR: Serial port ${SERIAL_PORT} not found." >&2
  exit 1
fi
if [[ "${USE_HARDWARE_BRIDGE}" == "true" && -e "${SERIAL_PORT}" && "$(command -v udevadm || true)" ]]; then
  SERIAL_PROPS="$(udevadm info --query=property --name="${SERIAL_PORT}" 2>/dev/null || true)"
  if ! grep -q '^ID_VENDOR_ID=1a86$' <<<"${SERIAL_PROPS}" || \
     ! grep -q '^ID_MODEL_ID=55d4$' <<<"${SERIAL_PROPS}"; then
    echo "[robot_start] ERROR: ${SERIAL_PORT} is not the Hiwonder WCH motor port (1a86:55d4)." >&2
    echo "[robot_start] ST-Link and native STM32 USB are separate diagnostic/programming paths." >&2
    exit 1
  fi
fi

# Validate camera reachability (best-effort)
CAMERA_IP="${CAMERA_IP_STATION:-192.168.1.125}"
USE_CAMERA_BRIDGE="${USE_CAMERA_BRIDGE:-false}"
if [[ "${USE_CAMERA_BRIDGE}" == "true" ]] && ! ping -c1 -W2 "${CAMERA_IP}" &>/dev/null; then
  echo "[robot_start] WARNING: Camera at ${CAMERA_IP} not reachable."
  echo "[robot_start] Camera bridge will start but may retry."
fi

# ── Source ROS2 workspace ──────────────────────────────────────────────────
# shellcheck source=/dev/null
set +u
source "${SCRIPT_DIR}/source_host_ws.sh"
set -u

# ── Launch ─────────────────────────────────────────────────────────────────
echo "[robot_start] Launching hardware bringup..."

exec ros2 launch robot_bringup rock64_bringup.launch.py \
  serial_port:="${SERIAL_PORT}" \
  use_hardware_bridge:="${USE_HARDWARE_BRIDGE}" \
  use_teleop:="${USE_TELEOP}" \
  use_audio:="${USE_AUDIO}" \
  monitor_battery:="${MONITOR_BATTERY}" \
  camera_ip:="${CAMERA_IP}" \
  use_camera_bridge:="${USE_CAMERA_BRIDGE}" \
  use_lidar:="${USE_LIDAR}" \
  lidar_serial_port:="${LIDAR_SERIAL_PORT}" \
  lidar_sync_gpiochip:="${LIDAR_SYNC_GPIOCHIP}" \
  use_usb_camera:="${USE_USB_CAMERA}" \
  usb_camera_device:="${USB_CAMERA_DEVICE}" \
  use_compressed_camera_transport:="${USE_COMPRESSED_CAMERA_TRANSPORT}" \
  camera_jpeg_quality:="${CAMERA_JPEG_QUALITY}"
