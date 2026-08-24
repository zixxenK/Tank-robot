#!/usr/bin/env bash
# MAINTENANCE ONLY: send one bounded direction command directly through the
# WCH STM32 link with the tracks raised. Normal driving uses ROS safety_gateway.
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 forward|back|stop [--confirm] [--seconds N] [--rps N]" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "${SCRIPT_DIR}/motor_command.py" "$@"
