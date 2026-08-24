#!/usr/bin/env bash
# Read-only diagnostics for the active drive/camera release path.
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

echo "=== Tank-robot diagnostics: $(hostname) - $(date) ==="
echo "Repository: ${REPO_ROOT}"

set +u
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/source_host_ws.sh"
set -u

echo
echo "--- Workspace ---"
if [[ -f "${HOST_WS_PATH}/install/setup.bash" ]]; then
  echo "OK: ${HOST_WS_PATH}/install/setup.bash"
else
  echo "MISSING: ${HOST_WS_PATH}/install/setup.bash"
  echo "Build with: bash scripts/unify_host_ws.sh --mode hardware --no-install-deps"
fi

echo
echo "--- Hardware service ---"
if command -v systemctl >/dev/null 2>&1 &&
   systemctl cat rock64-robot.service >/dev/null 2>&1; then
  systemctl is-active rock64-robot.service || true
  systemctl status rock64-robot.service --no-pager || true
else
  echo "rock64-robot.service is not installed (expected on a PC/WSL checkout)."
fi

echo
echo "--- Production serial link ---"
SERIAL_PORT="${SERIAL_PORT:-/dev/rock64_stm32}"
if [[ -e "${SERIAL_PORT}" ]]; then
  echo "OK: ${SERIAL_PORT}"
  if command -v udevadm >/dev/null 2>&1; then
    properties="$(udevadm info --query=property --name="${SERIAL_PORT}" 2>/dev/null || true)"
    if grep -q '^ID_VENDOR_ID=1a86$' <<<"${properties}" &&
       grep -q '^ID_MODEL_ID=55d4$' <<<"${properties}"; then
      echo "OK: Hiwonder WCH 1a86:55d4 (UART1/USART1 PA9-PA10)"
    else
      echo "ERROR: ${SERIAL_PORT} is not the expected Hiwonder WCH device"
    fi
  fi
else
  echo "MISSING: ${SERIAL_PORT}"
fi

echo
echo "--- Operator input ---"
PS5_JOY_DEVICE="${PS5_JOY_DEVICE:-/dev/input/ps5_controller}"
if [[ -e "${PS5_JOY_DEVICE}" ]]; then
  echo "OK: ${PS5_JOY_DEVICE}"
else
  echo "MISSING: ${PS5_JOY_DEVICE}"
  compgen -G "/dev/input/js*" >/dev/null && ls -l /dev/input/js* || true
fi

echo
echo "--- Camera reachability ---"
CAMERA_IP_STATION="${CAMERA_IP_STATION:-192.168.1.125}"
if command -v ping >/dev/null 2>&1 && ping -c 1 -W 1 "${CAMERA_IP_STATION}" >/dev/null 2>&1; then
  echo "OK: ESP32 camera host ${CAMERA_IP_STATION} responds"
else
  echo "WARN: ESP32 camera host ${CAMERA_IP_STATION} did not respond to ping"
fi
USB_CAMERA_DEVICE="${USB_CAMERA_DEVICE:-auto}"
if [[ "${USB_CAMERA_DEVICE}" == "auto" ]]; then
  USB_CAMERA_DEVICE="/dev/video0"
fi
if [[ -e "${USB_CAMERA_DEVICE}" ]]; then
  echo "OK: USB camera ${USB_CAMERA_DEVICE}"
else
  echo "WARN: USB camera ${USB_CAMERA_DEVICE} is not present"
fi

echo
echo "--- ROS graph ---"
NODE_LIST="$(ros2 node list 2>/dev/null || true)"
TOPIC_LIST="$(ros2 topic list 2>/dev/null || true)"
if [[ -n "${NODE_LIST}" ]]; then
  printf '%s\n' "${NODE_LIST}"
else
  echo "No ROS 2 nodes discovered. Check domain, middleware, and service state."
fi

echo
echo "Required release topics:"
for topic in \
  /stm32/bridge_alive \
  /stm32/encoder_ticks \
  /stm32/odom \
  /stm32/imu \
  /camera/image_raw \
  /camera/usb/image_raw \
  /stm32/diagnostics \
  /safety/diagnostics; do
  if grep -Fxq -- "${topic}" <<<"${TOPIC_LIST}"; then
    echo "OK: ${topic}"
  else
    echo "MISSING: ${topic}"
  fi
done

echo
echo "Optional topics (not release blockers):"
for topic in /scan /ultrasonic/range /stm32/battery; do
  if grep -Fxq -- "${topic}" <<<"${TOPIC_LIST}"; then
    echo "PRESENT: ${topic}"
  else
    echo "DISABLED/absent: ${topic}"
  fi
done

echo
echo "--- Git state ---"
git -C "${REPO_ROOT}" status --short --branch || true
echo "=== Diagnostics complete ==="
