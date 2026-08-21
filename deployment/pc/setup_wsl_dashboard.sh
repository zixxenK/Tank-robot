#!/usr/bin/env bash
# Install and build the PC-side ROS 2 dashboard stack in WSL2 Ubuntu 22.04.
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
ROS_DISTRO="${ROS_DISTRO:-humble}"

die() {
  echo "[pc_dashboard] ERROR: $*" >&2
  exit 1
}

[[ -f /etc/os-release ]] || die "WSL must provide /etc/os-release"
# shellcheck disable=SC1091
source /etc/os-release
[[ "${ID:-}" == "ubuntu" && "${VERSION_ID:-}" == "22.04" ]] || \
  die "This setup targets Ubuntu 22.04 in WSL2; found ${PRETTY_NAME:-unknown}. From PowerShell run: .\\deployment\\pc\\setup_dashboard.ps1"

[[ -f "/opt/ros/${ROS_DISTRO}/setup.bash" ]] || \
  die "ROS 2 ${ROS_DISTRO} is not installed in this WSL distribution"

echo "[pc_dashboard] Installing PC-side ROS dependencies..."
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
  "ros-${ROS_DISTRO}-foxglove-bridge" \
  "ros-${ROS_DISTRO}-slam-toolbox" \
  "ros-${ROS_DISTRO}-navigation2" \
  "ros-${ROS_DISTRO}-nav2-bringup" \
  "ros-${ROS_DISTRO}-rviz2" \
  "ros-${ROS_DISTRO}-image-transport" \
  "ros-${ROS_DISTRO}-image-transport-plugins" \
  "ros-${ROS_DISTRO}-cv-bridge" \
  "ros-${ROS_DISTRO}-rmw-fastrtps-cpp" \
  "ros-${ROS_DISTRO}-tf2-tools" \
  fastdds-tools \
  python3-colcon-common-extensions \
  python3-rosdep

# ROS setup scripts use optional variables without guarding them.  Source
# them with nounset disabled, then restore the script's strict mode.
set +u
# shellcheck disable=SC1091
source "/opt/ros/${ROS_DISTRO}/setup.bash"
set -u
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"
export ROS_LOCALHOST_ONLY="0"

if command -v rosdep >/dev/null 2>&1; then
  rosdep install --from-paths "${REPO_ROOT}/host_ws/src" --ignore-src -r -y
fi

echo "[pc_dashboard] Building the shared ROS workspace..."
cd "${REPO_ROOT}/host_ws"
colcon build --symlink-install \
  --packages-up-to robot_bringup robot_drivers robot_audio

echo "[pc_dashboard] Setup complete. Source deployment/pc/run_dashboard.sh to launch."
