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
TELEOP_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-teleop) TELEOP_OVERRIDE=false; shift ;;
    --teleop) TELEOP_OVERRIDE=true; shift ;;
    --help|-h)
      echo "usage: $0 [--teleop|--no-teleop]"
      exit 0
      ;;
    *)
      echo "[robot_start] ERROR: unknown option: $1" >&2
      exit 2
      ;;
  esac
done

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

export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"
export ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY:-0}"
if [[ "${ROCK64_USE_DISCOVERY_SERVER:-0}" == "1" || "${ROCK64_USE_DISCOVERY_SERVER:-0}" == "true" ]]; then
  if [[ -z "${ROS_DISCOVERY_SERVER:-}" && -z "${ROCK64_IP:-}" ]]; then
    echo "[robot_start] ERROR: discovery-server mode requires ROCK64_IP or ROS_DISCOVERY_SERVER." >&2
    exit 1
  fi
  export ROS_DISCOVERY_SERVER="${ROS_DISCOVERY_SERVER:-${ROCK64_IP}:11811}"
else
  unset ROS_DISCOVERY_SERVER
fi

# ── Environment detection & validation ────────────────────────────────────
echo "[robot_start] Rock64 Ranger starting..."
echo "[robot_start] Hostname : $(hostname)"
echo "[robot_start] Date     : $(date)"
echo "[robot_start] Repo root: ${REPO_ROOT}"
echo "[robot_start] Host WS  : $(resolve_host_ws)"

# Validate serial port
SERIAL_PORT="${SERIAL_PORT:-/dev/rock64_stm32}"
USE_HARDWARE_BRIDGE="${USE_HARDWARE_BRIDGE:-true}"
USE_TELEOP="${TELEOP_OVERRIDE:-${USE_TELEOP:-true}}"
PS5_JOY_DEVICE="${PS5_JOY_DEVICE:-/dev/input/ps5_controller}"
MONITOR_BATTERY="${MONITOR_BATTERY:-false}"
USE_AUDIO="${USE_AUDIO:-true}"
# LiDAR is optional and the canonical deployment config defaults it off until
# the UART and sync GPIO are physically commissioned. Do not surprise-boot a
# driver against an absent /dev/ttyS2 when the config file is missing.
USE_LIDAR="${USE_LIDAR:-false}"
LIDAR_SERIAL_PORT="${LIDAR_SERIAL_PORT:-/dev/ttyS2}"
LIDAR_SYNC_GPIOCHIP="${LIDAR_SYNC_GPIOCHIP:-/dev/gpiochip2}"
LIDAR_BAUDRATE="${LIDAR_BAUDRATE:-115200}"
LIDAR_USE_SYNC="${LIDAR_USE_SYNC:-true}"
USE_USB_CAMERA="${USE_USB_CAMERA:-true}"
USB_CAMERA_DEVICE="${USB_CAMERA_DEVICE:-auto}"
USE_ULTRASONIC="${USE_ULTRASONIC:-false}"
USE_COMPRESSED_CAMERA_TRANSPORT="${USE_COMPRESSED_CAMERA_TRANSPORT:-true}"
CAMERA_JPEG_QUALITY="${CAMERA_JPEG_QUALITY:-70}"

resolve_usb_camera_device() {
  local requested="$1"
  local camera_candidate
  if [[ "${requested}" != "auto" ]]; then
    echo "${requested}"
    return
  fi
  for camera_candidate in /dev/v4l/by-id/*-video-index0; do
    if [[ -e "${camera_candidate}" ]]; then
      echo "${camera_candidate}"
      return
    fi
  done
  echo "/dev/video0"
}

if [[ "${USE_USB_CAMERA}" == "true" ]]; then
  USB_CAMERA_DEVICE="$(resolve_usb_camera_device "${USB_CAMERA_DEVICE}")"
  echo "[robot_start] USB camera: ${USB_CAMERA_DEVICE}"
fi
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
USE_CAMERA_BRIDGE="${USE_CAMERA_BRIDGE:-true}"
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
  joy_device:="${PS5_JOY_DEVICE}" \
  use_audio:="${USE_AUDIO}" \
  monitor_battery:="${MONITOR_BATTERY}" \
  camera_ip:="${CAMERA_IP}" \
  use_camera_bridge:="${USE_CAMERA_BRIDGE}" \
  use_lidar:="${USE_LIDAR}" \
  lidar_serial_port:="${LIDAR_SERIAL_PORT}" \
  lidar_sync_gpiochip:="${LIDAR_SYNC_GPIOCHIP}" \
  lidar_baudrate:="${LIDAR_BAUDRATE}" \
  lidar_use_sync:="${LIDAR_USE_SYNC}" \
  use_usb_camera:="${USE_USB_CAMERA}" \
  usb_camera_device:="${USB_CAMERA_DEVICE}" \
  use_ultrasonic:="${USE_ULTRASONIC}" \
  use_compressed_camera_transport:="${USE_COMPRESSED_CAMERA_TRANSPORT}" \
  camera_jpeg_quality:="${CAMERA_JPEG_QUALITY}"
