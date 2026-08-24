#!/usr/bin/env bash
# Configure the canonical PS5 device path used by robot_start.sh.
#
# This replaces the obsolete approach of editing generated install YAML or
# adding an unused ps5_device launch argument. The source deployment config is
# the only persistent machine-local setting; robot_start.sh passes it as
# joy_device to rock64_bringup.launch.py.
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
CONFIG_FILE="${REPO_ROOT}/deployment/systemd/systemd_config.conf"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root so the service can be restarted: sudo bash $0" >&2
  exit 1
fi

detect_ps5_device() {
  if [[ -e /dev/input/ps5_controller ]]; then
    echo /dev/input/ps5_controller
    return
  fi
  if [[ -e /dev/input/ps5_controller_js ]]; then
    echo /dev/input/ps5_controller_js
    return
  fi
  if [[ -e /dev/input/js0 ]]; then
    echo /dev/input/js0
    return
  fi
  return 1
}

PS5_DEVICE="${1:-$(detect_ps5_device || true)}"
if [[ -z "${PS5_DEVICE}" || ! -e "${PS5_DEVICE}" ]]; then
  echo "No PS5 joystick device found. Pass its path explicitly." >&2
  echo "Example: sudo bash $0 /dev/input/ps5_controller" >&2
  exit 1
fi

if [[ ! -f "${CONFIG_FILE}" ]]; then
  echo "Missing ${CONFIG_FILE}; copy systemd_config.conf.example first." >&2
  exit 1
fi

backup="${CONFIG_FILE}.backup.$(date +%Y%m%d-%H%M%S)"
cp "${CONFIG_FILE}" "${backup}"
if grep -q '^PS5_JOY_DEVICE=' "${CONFIG_FILE}"; then
  sed -i "s|^PS5_JOY_DEVICE=.*|PS5_JOY_DEVICE=${PS5_DEVICE}|" "${CONFIG_FILE}"
else
  printf '\nPS5_JOY_DEVICE=%s\n' "${PS5_DEVICE}" >> "${CONFIG_FILE}"
fi

echo "Configured PS5 device: ${PS5_DEVICE}"
echo "Backup: ${backup}"

if command -v systemctl >/dev/null 2>&1 &&
   systemctl cat rock64-robot.service >/dev/null 2>&1; then
  systemctl restart rock64-robot.service
  systemctl is-active --quiet rock64-robot.service
  echo "rock64-robot.service restarted successfully."
else
  echo "rock64-robot.service is not installed; restart the canonical bringup manually."
fi

echo "Verify with: ros2 topic echo /teleop/ps5_status"
