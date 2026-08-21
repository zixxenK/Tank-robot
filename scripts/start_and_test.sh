#!/usr/bin/env bash
# Start the complete Rock64 stack and run the ordered, non-motion acceptance
# sequence in one operator command. Motors remain disabled by default.
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TRACKS_RAISED=false
REQUIRE_LIDAR=false

for arg in "$@"; do
  case "${arg}" in
    --tracks-raised) TRACKS_RAISED=true ;;
    --with-lidar|--require-lidar) REQUIRE_LIDAR=true ;;
    --no-lidar) REQUIRE_LIDAR=false ;;
    -h|--help)
      echo "usage: bash scripts/start_and_test.sh [--tracks-raised] [--with-lidar]"
      echo "Starts rock64-robot.service and runs all checks in order."
      echo "Motors are skipped unless --tracks-raised is explicitly supplied."
      exit 0
      ;;
    *) echo "unknown option: ${arg}" >&2; exit 2 ;;
  esac
done

set +u
# shellcheck source=/dev/null
source "${REPO_ROOT}/deployment/scripts/source_host_ws.sh"
set -u

echo "[start_and_test] spring-cleaning stale operator processes and ROS CLI state"
bash "${REPO_ROOT}/scripts/cleanup_runtime.sh"
echo "[start_and_test] restarting the single hardware owner: rock64-robot.service"
if [[ "$(id -u)" -eq 0 ]]; then
  systemctl restart rock64-robot.service
else
  sudo systemctl restart rock64-robot.service
fi
for _ in {1..30}; do
  systemctl is-active --quiet rock64-robot.service && break
  sleep 0.5
done
systemctl is-active --quiet rock64-robot.service || {
  echo "[start_and_test] ERROR: rock64-robot.service failed" >&2
  exit 1
}

echo "[start_and_test] ROS 2 stack is active; running ordered checks"
exec bash "${REPO_ROOT}/scripts/hardware_acceptance.sh" \
  $( [[ "${TRACKS_RAISED}" == true ]] && echo --tracks-raised ) \
  $( [[ "${REQUIRE_LIDAR}" == true ]] && echo --with-lidar || echo --no-lidar )
