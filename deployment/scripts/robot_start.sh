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
    echo "${HOST_WS_PATH}"
    return
  fi

  if [[ -d "${REPO_ROOT}/host_ws/src" ]]; then
    echo "${REPO_ROOT}/host_ws"
    return
  fi

  echo "${REPO_ROOT}/ros2_ws"
}

# ── Load deployment configuration ─────────────────────────────────────────
CONFIG_FILE="${DEPLOY_DIR}/systemd/systemd_config.conf"
if [[ -f "${CONFIG_FILE}" ]]; then
  # shellcheck source=/dev/null
  source "${CONFIG_FILE}"
fi

# ── Environment detection & validation ────────────────────────────────────
echo "[robot_start] Rock64 Ranger starting..."
echo "[robot_start] Hostname : $(hostname)"
echo "[robot_start] Date     : $(date)"
echo "[robot_start] Repo root: ${REPO_ROOT}"
echo "[robot_start] Host WS  : $(resolve_host_ws)"

# Validate serial port
SERIAL_PORT="${SERIAL_PORT:-/dev/rock64_stm32}"
if [[ ! -e "${SERIAL_PORT}" ]]; then
  echo "[robot_start] WARNING: Serial port ${SERIAL_PORT} not found."
  echo "[robot_start] STM32 motor bridge will start but may fail."
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
source "${SCRIPT_DIR}/source_ros2_ws.sh"

# ── Launch ─────────────────────────────────────────────────────────────────
echo "[robot_start] Launching hardware bringup..."
exec ros2 launch robot_bringup rock64_bringup.launch.py \
  host_workspace:="$(resolve_host_ws)" \
  serial_port:="${SERIAL_PORT}" \
  camera_ip:="${CAMERA_IP}" \
  use_camera_bridge:="${USE_CAMERA_BRIDGE}"
