#!/usr/bin/env bash
# Start the Rock64 ROS 2 base without requiring a PS5 controller.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ROS_DISTRO="${ROS_DISTRO:-humble}"

CONFIG_FILE="${REPO_ROOT}/deployment/systemd/systemd_config.conf"
set +u
if [[ -f "${CONFIG_FILE}" ]]; then
  # shellcheck source=/dev/null
  source "${CONFIG_FILE}"
fi
set -u
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"
export ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY:-0}"

set +u
# shellcheck source=/dev/null
source "/opt/ros/${ROS_DISTRO}/setup.bash"
if [[ -f "${REPO_ROOT}/host_ws/install/setup.bash" ]]; then
  # shellcheck source=/dev/null
  source "${REPO_ROOT}/host_ws/install/setup.bash"
else
  set -u
  echo "ROS 2 workspace is not built: ${REPO_ROOT}/host_ws/install/setup.bash" >&2
  echo "Build it with: cd ${REPO_ROOT}/host_ws && colcon build --symlink-install" >&2
  exit 4
fi
set -u

exec ros2 launch robot_bringup rock64_bringup.launch.py use_teleop:=false
