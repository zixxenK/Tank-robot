#!/usr/bin/env bash
# Compatibility name for the canonical bringup rebuild helper.
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "${SCRIPT_DIR}/rebuild_robot_bringup.sh" "$@"
