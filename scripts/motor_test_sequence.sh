#!/usr/bin/env bash
# Guarded sequence: forward -> stop -> back -> stop.
set -euo pipefail

if [[ "${1:-}" != "--confirm" ]]; then
  echo "usage: $0 --confirm [seconds]" >&2
  echo "Raise the tracks before running this movement sequence." >&2
  exit 3
fi

DURATION="${2:-1}"
if ! [[ "$DURATION" =~ ^[0-9]+([.][0-9]+)?$ ]] || [[ "$DURATION" == "0" ]]; then
  echo "duration must be a positive number of seconds" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"${SCRIPT_DIR}/motor_forward.sh" --confirm
sleep "$DURATION"
"${SCRIPT_DIR}/motor_stop.sh"
sleep 1
"${SCRIPT_DIR}/motor_back.sh" --confirm
sleep "$DURATION"
"${SCRIPT_DIR}/motor_stop.sh"
echo "movement sequence complete; stop sent"
