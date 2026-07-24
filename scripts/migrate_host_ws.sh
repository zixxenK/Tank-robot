#!/usr/bin/env bash
# migrate_host_ws.sh — Copy ROS2 packages from ros2_ws/src into host_ws/src.
# This is a non-destructive migration helper.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SRC_DIR="${REPO_ROOT}/ros2_ws/src"
DST_DIR="${REPO_ROOT}/host_ws/src"

if [[ ! -d "${SRC_DIR}" ]]; then
  echo "[migrate_host_ws] ERROR: Source workspace not found at ${SRC_DIR}" >&2
  exit 1
fi

mkdir -p "${DST_DIR}"

echo "[migrate_host_ws] Copying ROS2 packages from ${SRC_DIR} to ${DST_DIR}"
for pkg in "${SRC_DIR}"/*; do
  [[ -d "${pkg}" ]] || continue
  name="$(basename "${pkg}")"
  if [[ -e "${DST_DIR}/${name}" ]]; then
    echo "[migrate_host_ws] Skipping existing package: ${name}"
    continue
  fi
  cp -a "${pkg}" "${DST_DIR}/"
  echo "[migrate_host_ws] Copied: ${name}"
done

echo "[migrate_host_ws] Complete. Build with:"
echo "  cd ${REPO_ROOT}/host_ws"
echo "  colcon build --symlink-install"
