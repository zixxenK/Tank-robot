#!/usr/bin/env bash
# source_host_ws.sh — canonical ROS2 host workspace sourcing helper.
#
# Auto-detects the installed ROS2 distro (Humble-first policy) and
# sources both the base ROS2 installation and the active host workspace overlay.
#
# Usage: source source_host_ws.sh
set -eo pipefail  # Removed -u to allow undefined variables

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

  echo "[source_host_ws] ERROR: host_ws/src not found" >&2
  return 1
}

HOST_WS="$(resolve_host_ws)"

# A previous interactive build can leave another checkout in the overlay
# search paths (for example /home/rock64/install). Clear those paths before
# sourcing the canonical ROS installation, otherwise ros2 may launch stale
# nodes from the wrong workspace even when the current directory is correct.
unset AMENT_PREFIX_PATH CMAKE_PREFIX_PATH COLCON_PREFIX_PATH PYTHONPATH ROS_PACKAGE_PATH

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
      echo "[source_host_ws] ERROR: Auto ROS distro resolution only supports Ubuntu 22.04 (Humble)." >&2
      echo "[source_host_ws] Set ROS_DISTRO_OVERRIDE explicitly if you intentionally use another distro." >&2
      return 1
      ;;
  esac
}

DISTRO="$(resolve_ros_distro)"
ROS_BASE="/opt/ros/${DISTRO}"

if [[ ! -f "${ROS_BASE}/setup.bash" ]]; then
  echo "[source_host_ws] ERROR: ROS2 ${DISTRO} not found at ${ROS_BASE}"
  exit 1
fi

# shellcheck source=/dev/null
source "${ROS_BASE}/setup.bash"
echo "[source_host_ws] Sourced ROS2 ${DISTRO} from ${ROS_BASE}"
echo "[source_host_ws] Active host workspace: ${HOST_WS}"

# Source the workspace overlay if it has been built
INSTALL_SETUP="${HOST_WS}/install/setup.bash"
if [[ -f "${INSTALL_SETUP}" ]]; then
  # shellcheck source=/dev/null
  source "${INSTALL_SETUP}"
  echo "[source_host_ws] Sourced workspace overlay: ${INSTALL_SETUP}"
else
  echo "[source_host_ws] WARNING: Workspace not built yet."
  echo "[source_host_ws] Run: cd ${HOST_WS} && colcon build"
fi

export ROS_DISTRO="${DISTRO}"
export HOST_WS_PATH="${HOST_WS}"
