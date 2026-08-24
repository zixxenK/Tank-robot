#!/usr/bin/env bash
# Compatibility wrapper for the historical WSL Gazebo setup entry point.
# The canonical dependency, build, and launch workflow lives in
# scripts/unify_host_ws.sh so this name cannot drift into a second setup path.
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

echo "[setup_wsl_gazebo] Delegating to the canonical host-workspace workflow."
exec bash "${REPO_ROOT}/scripts/unify_host_ws.sh" --mode sim
