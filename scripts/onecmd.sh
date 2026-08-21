#!/usr/bin/env bash
# One-command Rock64 hardware startup. Pass --sim for Gazebo instead.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
MODE="hardware"
FORCE_ALL_HARDWARE="true"
ROBOT_SERVICE="rock64-robot.service"

as_root() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --sim)
      MODE="sim"
      shift
      ;;
    --hardware)
      MODE="hardware"
      shift
      ;;
    --configured)
      FORCE_ALL_HARDWARE="false"
      shift
      ;;
    --test)
      # Start the service and immediately run the ordered safe acceptance
      # checks. This keeps startup and validation as one operator command.
      exec bash "${REPO_ROOT}/scripts/start_and_test.sh" "${@:2}"
      ;;
    --help|-h)
      echo "usage: $0 [--sim|--hardware] [--configured] [--test] [name:=value ...]"
      echo "default: launch the persistent STM32 + PS5 + ESP32 + USB-camera stack"
      echo "--configured: honor hardware enable/disable values from deployment config"
      echo "--test: restart the stack and run the ordered non-motion acceptance checks"
      exit 0
      ;;
    *)
      break
      ;;
  esac
done

set +u
# shellcheck source=/dev/null
source "${REPO_ROOT}/deployment/scripts/source_host_ws.sh"
set -u

bash "${REPO_ROOT}/scripts/cleanup_runtime.sh"

cd "${HOST_WS_PATH}"
if [[ "${MODE}" == "sim" ]]; then
  exec ros2 launch robot_bringup gazebo_telemetry.launch.py "$@"
fi

# The persistent service is the sole owner of the STM32 UART. Restarting it
# applies the deployed all-hardware configuration without opening a competing
# foreground serial bridge.
if command -v systemctl >/dev/null 2>&1 && \
   systemctl cat "${ROBOT_SERVICE}" >/dev/null 2>&1; then
  echo "[onecmd] Starting/restarting ${ROBOT_SERVICE}; it is the sole hardware owner."
  as_root systemctl restart "${ROBOT_SERVICE}"
  systemctl is-active --quiet "${ROBOT_SERVICE}" || {
    echo "[onecmd] ERROR: ${ROBOT_SERVICE} did not restart successfully." >&2
    exit 1
  }
  echo "[onecmd] All-hardware service is active."
  echo "[onecmd] Ordered test command: bash ${REPO_ROOT}/scripts/hardware_acceptance.sh"
  exit 0
fi

if [[ "${USE_USB_CAMERA:-true}" == "true" && "${USB_CAMERA_DEVICE:-auto}" == "auto" ]]; then
  resolved_camera_device="/dev/video0"
  for camera_candidate in /dev/v4l/by-id/*-video-index0; do
    if [[ -e "${camera_candidate}" ]]; then
      resolved_camera_device="${camera_candidate}"
      break
    fi
  done
  export USB_CAMERA_DEVICE="${resolved_camera_device}"
fi

if [[ "${FORCE_ALL_HARDWARE}" == "true" ]]; then
  exec ros2 launch robot_bringup rock64_bringup.launch.py \
    use_hardware_bridge:=true \
    use_teleop:=true \
    use_camera_bridge:=true \
    use_usb_camera:=true \
    use_compressed_camera_transport:=true \
    "$@"
fi

exec ros2 launch robot_bringup rock64_bringup.launch.py "$@"
