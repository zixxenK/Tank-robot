#!/usr/bin/env bash
# Install the repository's canonical DualSense udev rule and refresh udev.
# This helper changes device permissions only; it never edits ROS launch files.
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
RULE_SOURCE="${REPO_ROOT}/deployment/udev/99-rock64-ps5.rules"
RULE_TARGET="/etc/udev/rules.d/99-rock64-ps5.rules"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "[fix_input_permissions] ERROR: run as root: sudo bash $0" >&2
  exit 1
fi
if [[ ! -f "${RULE_SOURCE}" ]]; then
  echo "[fix_input_permissions] ERROR: missing ${RULE_SOURCE}" >&2
  exit 1
fi

install -D -m 0644 "${RULE_SOURCE}" "${RULE_TARGET}"
if id rock64 >/dev/null 2>&1 && getent group input >/dev/null 2>&1; then
  usermod -aG input rock64
fi
udevadm control --reload-rules
udevadm trigger --subsystem-match=input
udevadm settle

echo "[fix_input_permissions] Installed ${RULE_TARGET}."
echo "[fix_input_permissions] Stable device: /dev/input/ps5_controller"
echo "[fix_input_permissions] Verify with: bash deployment/scripts/quick_ps5_test.sh"
