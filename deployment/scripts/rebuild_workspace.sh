#!/usr/bin/env bash
# Complete rebuild of the canonical ROS 2 workspace.
#
# This historical entry point is retained for operator compatibility.  It
# deliberately rebuilds every package under host_ws/src so removed or newly
# added lab-assistant packages cannot remain stale in install/.
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
WS_PATH="${REPO_ROOT}/host_ws"

if [[ ! -d "${WS_PATH}/src" ]]; then
  echo "[rebuild_workspace] ERROR: workspace not found at ${WS_PATH}/src" >&2
  exit 1
fi

cd "${WS_PATH}"
echo "[rebuild_workspace] Removing generated ROS state from ${WS_PATH}"
rm -rf build install log

export HOST_WS_PATH="${WS_PATH}"
set +u
# shellcheck disable=SC1091
source "${REPO_ROOT}/deployment/scripts/source_host_ws.sh"
set -u

echo "[rebuild_workspace] Installing package dependencies"
rosdep install --from-paths src --ignore-src -r -y

echo "[rebuild_workspace] Building all packages under host_ws/src"
colcon build --symlink-install

if [[ ! -f install/setup.bash ]]; then
  echo "[rebuild_workspace] ERROR: install/setup.bash was not generated" >&2
  exit 1
fi

echo "[rebuild_workspace] Complete. Restart with:"
echo "  sudo systemctl restart rock64-robot.service"
