#!/usr/bin/env bash
# MAINTENANCE ONLY: direct stop helper for a raised-track UART proof.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${SCRIPT_DIR}/motor_direction.sh" stop
