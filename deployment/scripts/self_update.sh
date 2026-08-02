#!/usr/bin/env bash
# Safe git pull plus conditional rebuild. Firmware is never auto-flashed.
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
BRANCH="${TANK_ROBOT_BRANCH:-main}"
LOCK_FILE="/tmp/tank-robot-self-update.lock"

cd "${REPO_ROOT}"
exec 200>"${LOCK_FILE}"
flock -n 200 || { echo "[self_update] Update already running - exiting."; exit 0; }

if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo "[self_update] Tracked local changes present - refusing to pull. Resolve manually." >&2
  exit 1
fi

CURRENT_SHA="$(git rev-parse HEAD)"
git fetch origin "${BRANCH}" --quiet
REMOTE_SHA="$(git rev-parse "origin/${BRANCH}")"

if [[ "${CURRENT_SHA}" == "${REMOTE_SHA}" ]]; then
  echo "[self_update] Already up to date (${CURRENT_SHA:0:8})."
  exit 0
fi

echo "[self_update] ${CURRENT_SHA:0:8} -> ${REMOTE_SHA:0:8}"
git merge --ff-only "origin/${BRANCH}"

if git diff --name-only "${CURRENT_SHA}" "${REMOTE_SHA}" | grep -q '^host_ws/'; then
  echo "[self_update] host_ws changed - rebuilding."
  # shellcheck source=/dev/null
  source "${SCRIPT_DIR}/source_host_ws.sh"
  cd "${HOST_WS_PATH}"
  rosdep install --from-paths src --ignore-src -r -y
  colcon build --symlink-install
fi

if git diff --name-only "${CURRENT_SHA}" "${REMOTE_SHA}" | grep -q '^firmware/'; then
  echo "[self_update] firmware/ changed - NOT auto-flashing STM32. Flash manually: make stm32-flash"
fi

echo "[self_update] Done at $(date)."