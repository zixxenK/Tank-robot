#!/usr/bin/env bash
# Unified, portable self-diagnostic for Tank-robot.
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Tank-robot Diagnostics - $(hostname) - $(date) ==="

echo; echo "--- Environment ---"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/source_host_ws.sh"

echo; echo "--- Build health ---"
cd "${HOST_WS_PATH}"
if [[ -d src/ros_robot_controller || -d src/ros_robot_controller_msgs ]]; then
  echo "WARNING: orphaned ros_robot_controller package(s) still present"
fi
if [[ ! -f install/setup.bash ]]; then
  echo "WARNING: workspace not built. Run: colcon build --symlink-install"
fi

echo; echo "--- systemd service (Rock64 only) ---"
if command -v systemctl >/dev/null 2>&1 \
   && systemctl list-unit-files 2>/dev/null | grep -q rock64-robot.service; then
  systemctl status rock64-robot.service --no-pager || true
  echo
  journalctl -u rock64-robot.service -n 50 --no-pager || true
else
  echo "rock64-robot.service not installed (expected on local PC / WSL dev)."
fi

echo; echo "--- ROS graph ---"
if ros2 node list >/dev/null 2>&1; then
  ros2 node list
  echo
  ros2 topic list
else
  echo "No ROS2 daemon reachable - nothing running, or RMW/domain mismatch."
fi

echo; echo "--- Serial hardware ---"
SERIAL_PORT="${SERIAL_PORT:-/dev/rock64_stm32}"
if [[ -e "${SERIAL_PORT}" ]]; then
  echo "OK: ${SERIAL_PORT} present"
else
  echo "MISSING: ${SERIAL_PORT} (expected off-hardware on local PC / WSL)"
fi

echo; echo "--- Network and Hiwonder WCH USART1 host (PA9/PA10; product UART1) hardware ---"
ip -brief link 2>/dev/null || true
if command -v nmcli >/dev/null 2>&1; then
  nmcli --terse --fields DEVICE,TYPE,STATE,CONNECTION device status || true
fi
if command -v rfkill >/dev/null 2>&1; then
  rfkill list || true
fi
if command -v lsusb >/dev/null 2>&1; then
  lsusb || true
fi

echo; echo "--- Operator input devices ---"
if compgen -G "/dev/input/event*" >/dev/null; then
  ls -l /dev/input/event* || true
else
  echo "No /dev/input/event* devices detected."
fi

echo; echo "--- ESP32 camera reachability ---"
CAMERA_IP_STATION="${CAMERA_IP_STATION:-192.168.1.125}"
if ping -c 1 -W 1 "${CAMERA_IP_STATION}" >/dev/null 2>&1; then
  echo "OK: camera host ${CAMERA_IP_STATION} responds"
else
  echo "UNREACHABLE: camera host ${CAMERA_IP_STATION}"
fi

echo; echo "--- git state ---"
git -C "${REPO_ROOT}" status --short --branch || true

echo; echo "=== Diagnostics complete ==="
