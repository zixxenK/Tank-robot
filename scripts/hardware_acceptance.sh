#!/usr/bin/env bash
# Run the ordered ROS 2 hardware checks against an already-running Rock64 stack.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TRACKS_RAISED="false"
REQUIRE_LIDAR="false"
REQUIRE_IMU="true"
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
    --tracks-raised)
      TRACKS_RAISED="true"
      shift
      ;;
    --with-lidar|--require-lidar)
      REQUIRE_LIDAR="true"
      shift
      ;;
    --no-lidar)
      REQUIRE_LIDAR="false"
      shift
      ;;
    --no-imu)
      REQUIRE_IMU="false"
      shift
      ;;
    --help|-h)
      echo "usage: $0 [--tracks-raised] [--with-lidar|--no-lidar] [--no-imu]"
      echo "Runs the drive/camera acceptance checks against the active ROS 2 graph."
      echo "Motor motion is skipped unless --tracks-raised is supplied."
      exit 0
      ;;
    *)
      echo "unknown option: $1" >&2
      exit 2
      ;;
  esac
done

# The shared source helper exports the deployment config, ensuring this process
# joins the same DDS graph as rock64-robot.service.
set +u
# shellcheck source=/dev/null
source "${REPO_ROOT}/deployment/scripts/source_host_ws.sh"
set -u

# The acceptance runner is a direct rclpy process and must not inherit a stale
# ros2cli daemon from an older checkout/domain. Stopping the daemon is safe and
# does not stop the persistent hardware nodes.
ros2 daemon stop >/dev/null 2>&1 || true

# Attach to the persistent graph. If the installed unit is stopped, starting
# it here makes this script the only command needed for the complete test run.
# This script never launches another hardware bridge of its own.
if command -v systemctl >/dev/null 2>&1 && \
   systemctl cat "${ROBOT_SERVICE}" >/dev/null 2>&1; then
  if systemctl is-active --quiet "${ROBOT_SERVICE}"; then
    echo "[hardware_acceptance] Attaching to active ${ROBOT_SERVICE}."
  else
    echo "[hardware_acceptance] Starting ${ROBOT_SERVICE}..."
    as_root systemctl start "${ROBOT_SERVICE}"
    for _ in {1..20}; do
      systemctl is-active --quiet "${ROBOT_SERVICE}" && break
      sleep 0.5
    done
    if ! systemctl is-active --quiet "${ROBOT_SERVICE}"; then
      echo "[hardware_acceptance] ERROR: ${ROBOT_SERVICE} failed to start." >&2
      systemctl --no-pager --full status "${ROBOT_SERVICE}" >&2 || true
      exit 1
    fi
    # Type=simple becomes active before all ROS publishers are discoverable.
    sleep 2
  fi
else
  echo "[hardware_acceptance] No installed ${ROBOT_SERVICE}; testing the existing ROS 2 graph only."
fi

if [[ "${TRACKS_RAISED}" == "true" ]]; then
  echo "[hardware_acceptance] Tracks-raised motor checks ENABLED."
else
  echo "[hardware_acceptance] Motor motion disabled; pass --tracks-raised only on a secured bench."
fi

exec ros2 run robot_drivers hardware_test_runner --ros-args \
  -p tracks_raised:="${TRACKS_RAISED}" \
  -p require_lidar:="${REQUIRE_LIDAR}" \
  -p require_imu:="${REQUIRE_IMU}" \
  -p require_ultrasonic:=false \
  -p require_servo:=false
