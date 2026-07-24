#!/usr/bin/env bash
# source_ros2_ws.sh — ROS2 workspace sourcing helper.
#
# Auto-detects the installed ROS2 distro (Humble-first policy) and
# sources both the base ROS2 installation and the active host workspace overlay.
#
# Usage: source source_ros2_ws.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

resolve_host_ws() {
  if [[ -n "${HOST_WS_PATH:-}" ]]; then
    echo "${HOST_WS_PATH}"
    return
  fi

  if [[ -d "${REPO_ROOT}/host_ws/src" ]]; then
    echo "${REPO_ROOT}/host_ws"
    return
  fi

  echo "${REPO_ROOT}/ros2_ws"
}

ROS2_WS="$(resolve_host_ws)"

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
  # Ubuntu 22.04 -> Humble
  local ubuntu_version
  ubuntu_version=$(lsb_release -rs 2>/dev/null || echo "0")
  case "${ubuntu_version}" in
    22.*)  echo "humble" ;;
    *)
      echo "[source_ros2_ws] ERROR: Auto ROS distro resolution only supports Ubuntu 22.04 (Humble)." >&2
      echo "[source_ros2_ws] Set ROS_DISTRO_OVERRIDE explicitly if you intentionally use another distro." >&2
      return 1
      ;;
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
echo "[source_ros2_ws] Active host workspace: ${ROS2_WS}"

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
export HOST_WS_PATH="${ROS2_WS}"
