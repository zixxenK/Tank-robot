#!/usr/bin/env bash
# Rebuild the canonical bringup dependency closure after a launch/config change.
# Kept under its historical name for operator compatibility.
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
export HOST_WS_PATH="${REPO_ROOT}/host_ws"

set +u
# shellcheck disable=SC1091
source "${REPO_ROOT}/deployment/scripts/source_host_ws.sh"
set -u

cd "${HOST_WS_PATH}"
colcon build --symlink-install

if command -v systemctl >/dev/null 2>&1 &&
   systemctl cat rock64-robot.service >/dev/null 2>&1; then
  if [[ "$(id -u)" -eq 0 ]]; then
    systemctl restart rock64-robot.service
  else
    sudo systemctl restart rock64-robot.service
  fi
  systemctl is-active --quiet rock64-robot.service
  echo "[rebuild_robot_bringup] rock64-robot.service is active."
else
  echo "[rebuild_robot_bringup] No service installed; build completed."
fi
