#!/usr/bin/env bash
# Start both tracks forward through the single STM32 bridge.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${SCRIPT_DIR}/motor_direction.sh" forward "$@"
