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

[[ "${ROS_DISTRO}" == "humble" ]] || \
  die "This repository supports ROS 2 Humble; found ROS_DISTRO=${ROS_DISTRO}"

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

# Use the same ROS/workspace helper as Rock64 launch and build scripts. This
# makes the PC dashboard consume the exact same host_ws source tree and map.
export HOST_WS_PATH="${REPO_ROOT}/host_ws"
set +u
# shellcheck disable=SC1091
source "${REPO_ROOT}/deployment/scripts/source_host_ws.sh"
set -u
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"
export ROS_LOCALHOST_ONLY="0"

if command -v rosdep >/dev/null 2>&1; then
  rosdep install --from-paths "${REPO_ROOT}/host_ws/src" --ignore-src -r -y
fi

echo "[pc_dashboard] Building the shared ROS workspace..."
cd "${HOST_WS_PATH}"
colcon build --symlink-install

echo "[pc_dashboard] Setup complete. Source deployment/pc/run_dashboard.sh to launch."
