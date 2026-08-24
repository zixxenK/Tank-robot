#!/usr/bin/env bash
# Start the PC-side read-only Foxglove/SLAM graph.
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
export HOST_WS_PATH="${REPO_ROOT}/host_ws"
# Use the canonical base/workspace sourcing helper so this dashboard cannot
# accidentally attach to a different checkout or stale ROS overlay.
set +u
# shellcheck disable=SC1091
source "${REPO_ROOT}/deployment/scripts/source_host_ws.sh"
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

exec ros2 launch robot_bringup pc_dashboard.launch.py "$@"
