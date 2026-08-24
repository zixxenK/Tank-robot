#!/usr/bin/env bash
# MAINTENANCE ONLY: raised-track reverse proof through the WCH STM32 link.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${SCRIPT_DIR}/motor_direction.sh" back "$@"
