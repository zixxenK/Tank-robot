#!/usr/bin/env bash
# Start the PC-side read-only Foxglove/SLAM graph.
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
ROS_DISTRO="${ROS_DISTRO:-humble}"

# ROS setup scripts use optional variables without guarding them.  Source
# both layers with nounset disabled, then restore the launcher strict mode.
set +u
# shellcheck disable=SC1091
source "/opt/ros/${ROS_DISTRO}/setup.bash"
source "${REPO_ROOT}/host_ws/install/setup.bash"
set -u

die() {
  echo "[pc_dashboard] ERROR: $*" >&2
  exit 1
}

command -v ros2 >/dev/null 2>&1 || die "ROS 2 is not available in this WSL distribution"
ros2 pkg prefix foxglove_bridge >/dev/null 2>&1 || \
  die "foxglove_bridge is not installed; run .\\deployment\\pc\\setup_dashboard.ps1 from PowerShell"
if [[ "${*:-}" != *"use_slam:=false"* ]]; then
  ros2 pkg prefix slam_toolbox >/dev/null 2>&1 || \
    die "slam_toolbox is not installed; run .\\deployment\\pc\\setup_dashboard.ps1 from PowerShell"
fi

export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"
export ROS_LOCALHOST_ONLY="0"
# The Rock64 hosts the deterministic discovery server so WSL NAT does not
# have to carry DDS multicast between the PC and the robot.
export ROS_DISCOVERY_SERVER="${ROS_DISCOVERY_SERVER:-192.168.1.139:11811}"

exec ros2 launch robot_bringup pc_dashboard.launch.py "$@"
