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
if command -v timeout >/dev/null 2>&1; then
  NODE_LIST="$(timeout 8 ros2 node list 2>/dev/null || true)"
  TOPIC_LIST="$(timeout 8 ros2 topic list 2>/dev/null || true)"
else
  NODE_LIST="$(ros2 node list 2>/dev/null || true)"
  TOPIC_LIST="$(ros2 topic list 2>/dev/null || true)"
fi
if [[ -n "${NODE_LIST}" ]]; then
  printf '%s\n' "${NODE_LIST}"
  echo
  printf '%s\n' "${TOPIC_LIST}"
else
  echo "No ROS2 nodes discovered - nothing running, or RMW/domain mismatch."
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
  if command -v curl >/dev/null 2>&1; then
    curl --connect-timeout 2 --max-time 3 -sS -o /dev/null \
      -w "ESP32 MJPEG HTTP: status=%{http_code} bytes=%{size_download}\n" \
      "http://${CAMERA_IP_STATION}:81/stream" || true
  fi
else
  echo "UNREACHABLE: camera host ${CAMERA_IP_STATION}"
fi

echo; echo "--- Sensor acquisition paths ---"
DIAGNOSTIC_CAMERA_DEVICE="${USB_CAMERA_DEVICE:-/dev/video0}"
if [[ "${DIAGNOSTIC_CAMERA_DEVICE}" == "auto" ]]; then
  DIAGNOSTIC_CAMERA_DEVICE="/dev/video0"
  for camera_candidate in /dev/v4l/by-id/*-video-index0; do
    if [[ -e "${camera_candidate}" ]]; then
      DIAGNOSTIC_CAMERA_DEVICE="${camera_candidate}"
      break
    fi
  done
fi
for device in "${SERIAL_PORT}" /dev/ttyS2 /dev/gpiochip2 "${DIAGNOSTIC_CAMERA_DEVICE}"; do
  if [[ -e "${device}" ]]; then
    echo "OK: ${device} present"
  else
    echo "MISSING: ${device}"
  fi
done

for topic in \
  /ultrasonic/range \
  /scan \
  /camera/image_raw/compressed \
  /camera/usb/image_raw/compressed \
  /stm32/diagnostics \
  /lidar/diagnostics \
  /camera/diagnostics \
  /camera/usb/diagnostics; do
  if grep -Fqx -- "${topic}" <<<"${TOPIC_LIST}"; then
    echo "OK: ROS topic ${topic} exists"
  else
    echo "MISSING: ROS topic ${topic}"
  fi
done

echo; echo "--- git state ---"
git -C "${REPO_ROOT}" status --short --branch || true

echo; echo "=== Diagnostics complete ==="
