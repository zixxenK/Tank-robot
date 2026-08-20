#!/usr/bin/env bash
# Start the PC-side read-only Foxglove/SLAM graph.
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
ROS_DISTRO="${ROS_DISTRO:-humble}"

# shellcheck disable=SC1091
source "/opt/ros/${ROS_DISTRO}/setup.bash"
source "${REPO_ROOT}/host_ws/install/setup.bash"

export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"
export ROS_LOCALHOST_ONLY="0"

exec ros2 launch robot_bringup pc_dashboard.launch.py "$@"
