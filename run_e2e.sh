#!/usr/bin/env bash
# Human-first one-shot E2E entry point.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if command -v python3 >/dev/null 2>&1; then
  exec python3 "${SCRIPT_DIR}/scripts/e2e_mission.py"
fi

exec python "${SCRIPT_DIR}/scripts/e2e_mission.py"
