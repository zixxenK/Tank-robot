#!/usr/bin/env bash
# source_ros2_ws.sh — ROS2 workspace sourcing helper.
#
# Auto-detects the installed ROS2 distro (Jazzy or Humble) and
# sources both the base ROS2 installation and the local ros2_ws overlay.
#
# Usage: source source_ros2_ws.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
ROS2_WS="${REPO_ROOT}/ros2_ws"

# ── Auto-detect ROS distro ────────────────────────────────────────────────
resolve_ros_distro() {
  # Explicit override from environment
  if [[ -n "${ROS_DISTRO_OVERRIDE:-}" ]]; then
    echo "${ROS_DISTRO_OVERRIDE}"
    return
  fi
  # Already set by the calling environment
  if [[ -n "${ROS_DISTRO:-}" && "${ROS_DISTRO}" != "auto" ]]; then
    echo "${ROS_DISTRO}"
    return
  fi
  # Detect from Ubuntu version
  # Ubuntu 24.04 -> Jazzy, Ubuntu 22.04 -> Humble
  local ubuntu_version
  ubuntu_version=$(lsb_release -rs 2>/dev/null || echo "0")
  case "${ubuntu_version}" in
    24.*)  echo "jazzy"  ;;
    22.*)  echo "humble" ;;
    *)     echo "jazzy"  ;;  # default to latest
  esac
}

DISTRO="$(resolve_ros_distro)"
ROS_BASE="/opt/ros/${DISTRO}"

if [[ ! -f "${ROS_BASE}/setup.bash" ]]; then
  echo "[source_ros2_ws] ERROR: ROS2 ${DISTRO} not found at ${ROS_BASE}"
  exit 1
fi

# shellcheck source=/dev/null
source "${ROS_BASE}/setup.bash"
echo "[source_ros2_ws] Sourced ROS2 ${DISTRO} from ${ROS_BASE}"

# Source the workspace overlay if it has been built
INSTALL_SETUP="${ROS2_WS}/install/setup.bash"
if [[ -f "${INSTALL_SETUP}" ]]; then
  # shellcheck source=/dev/null
  source "${INSTALL_SETUP}"
  echo "[source_ros2_ws] Sourced workspace overlay: ${INSTALL_SETUP}"
else
  echo "[source_ros2_ws] WARNING: Workspace not built yet."
  echo "[source_ros2_ws] Run: cd ${ROS2_WS} && colcon build"
fi

export ROS_DISTRO="${DISTRO}"
