#!/usr/bin/env bash
# Compatibility name for the canonical PS5 device configuration helper.
# The historical script edited ROS environment/configuration ad hoc and could
# leave an unused PS5_DEVICE variable behind. Keep detection and persistence
# in one implementation.
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "${SCRIPT_DIR}/fix_ps5_device_path.sh" "$@"
