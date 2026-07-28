#!/bin/sh
# One-command Gazebo launch for a prepared host workspace.
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd)

resolve_host_ws() {
  if [ -n "${HOST_WS_PATH:-}" ] && [ -d "${HOST_WS_PATH}/src" ]; then
    printf '%s\n' "${HOST_WS_PATH}"
    return 0
  fi

  if [ -d "${REPO_ROOT}/host_ws/src" ]; then
    printf '%s\n' "${REPO_ROOT}/host_ws"
    return 0
  fi

  printf '%s\n' "${REPO_ROOT}/ros2_ws"
}

HOST_WS=$(resolve_host_ws)

if [ ! -f /opt/ros/humble/setup.bash ]; then
  echo "[onecmd] ROS2 Humble not found at /opt/ros/humble/setup.bash" >&2
  exit 3
fi

cd "${HOST_WS}"
. /opt/ros/humble/setup.bash
if [ -f install/setup.bash ]; then
  . install/setup.bash
fi

exec ros2 launch robot_bringup gazebo_telemetry.launch.py