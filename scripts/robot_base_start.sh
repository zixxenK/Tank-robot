#!/usr/bin/env bash
# Compatibility wrapper: start the canonical Rock64 bringup without teleop.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

exec bash "${REPO_ROOT}/deployment/scripts/robot_start.sh" --no-teleop
