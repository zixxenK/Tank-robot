#!/usr/bin/env bash
# Non-invasive PS5 input diagnostic for the canonical teleop path.
#
# This script may start a temporary joy_node, but it never starts a motor
# bridge, publishes /cmd_vel, or restarts the hardware service. Normal driving
# remains owned by rock64_bringup.launch.py and safety_gateway.
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
JOY_DEVICE="${PS5_JOY_DEVICE:-/dev/input/ps5_controller}"

if [[ "${JOY_DEVICE}" == "auto" ]]; then
  JOY_DEVICE=""
  for candidate in /dev/input/ps5_controller /dev/input/ps5_controller_js /dev/input/js*; do
    if [[ -e "${candidate}" ]]; then
      JOY_DEVICE="${candidate}"
      break
    fi
  done
fi

if [[ -z "${JOY_DEVICE}" || ! -e "${JOY_DEVICE}" ]]; then
  echo "[quick_ps5_test] ERROR: no PS5 joystick at ${JOY_DEVICE:-auto}" >&2
  echo "[quick_ps5_test] Connect the controller or set PS5_JOY_DEVICE explicitly." >&2
  ls -la /dev/input 2>/dev/null || true
  exit 1
fi

command -v ros2 >/dev/null 2>&1 || {
  echo "[quick_ps5_test] ERROR: ROS 2 is not available." >&2
  exit 1
}
command -v timeout >/dev/null 2>&1 || {
  echo "[quick_ps5_test] ERROR: timeout is required for the bounded diagnostic." >&2
  exit 1
}

set +u
# shellcheck disable=SC1091
source "${REPO_ROOT}/deployment/scripts/source_host_ws.sh"
set -u

if command -v jstest >/dev/null 2>&1; then
  echo "[quick_ps5_test] Reading ${JOY_DEVICE} for up to 10 seconds; press controls."
  timeout 10 jstest "${JOY_DEVICE}" || true
else
  echo "[quick_ps5_test] jstest is not installed; skipping raw joystick display."
  echo "[quick_ps5_test] Install it with: sudo apt-get install joystick"
fi

JOY_PID=""
cleanup() {
  if [[ -n "${JOY_PID}" ]]; then
    kill "${JOY_PID}" 2>/dev/null || true
    wait "${JOY_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "[quick_ps5_test] Starting temporary joy_node for 5 seconds."
ros2 run joy joy_node --ros-args -p dev:="${JOY_DEVICE}" &
JOY_PID=$!
sleep 2

if ros2 topic list | grep -Fxq "/joy"; then
  echo "[quick_ps5_test] PASS: /joy exists. Move a stick and capture one message."
  timeout 3 ros2 topic echo /joy --once || true
else
  echo "[quick_ps5_test] FAIL: /joy was not discovered." >&2
  exit 1
fi

echo "[quick_ps5_test] Canonical operator launch:"
echo "  ros2 launch robot_bringup rock64_bringup.launch.py joy_device:=${JOY_DEVICE}"
