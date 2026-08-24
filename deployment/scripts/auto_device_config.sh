#!/usr/bin/env bash
# Reconcile a newly plugged WCH motor UART with the canonical Rock64 config.
# Only the verified Hiwonder WCH VID/PID is accepted; generic serial devices
# and ST-Link/native USB are never selected as the motor transport.
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-/opt/rock64-robot}"
if [[ ! -d "${REPO_ROOT}/deployment" ]]; then
  REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
fi

RESTART=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --restart) RESTART=true; shift ;;
    --help|-h)
      echo "usage: sudo bash $0 [--restart]"
      echo "Finds only WCH 1a86:55d4 and configures /dev/rock64_stm32."
      exit 0
      ;;
    *) echo "[auto_device_config] ERROR: unknown option: $1" >&2; exit 2 ;;
  esac
done

if [[ "$(id -u)" -ne 0 ]]; then
  echo "[auto_device_config] ERROR: run as root: sudo bash $0" >&2
  exit 1
fi
command -v udevadm >/dev/null 2>&1 || {
  echo "[auto_device_config] ERROR: udevadm is required" >&2
  exit 1
}

mapfile -t wch_devices < <(
  shopt -s nullglob
  for device in /dev/ttyUSB* /dev/ttyACM*; do
    properties="$(udevadm info --query=property --name="${device}" 2>/dev/null || true)"
    if grep -q '^ID_VENDOR_ID=1a86$' <<<"${properties}" &&
       grep -q '^ID_MODEL_ID=55d4$' <<<"${properties}"; then
      printf '%s\n' "${device}"
    fi
  done
)

if (( ${#wch_devices[@]} == 0 )); then
  echo "[auto_device_config] ERROR: no Hiwonder WCH motor UART (1a86:55d4) found." >&2
  echo "[auto_device_config] ST-Link/native USB/generic UART devices are not valid replacements." >&2
  exit 1
fi
if (( ${#wch_devices[@]} > 1 )); then
  printf '[auto_device_config] ERROR: multiple WCH candidates found: %s\n' "${wch_devices[*]}" >&2
  echo "[auto_device_config] Disconnect the extra adapter before configuring the robot." >&2
  exit 1
fi

RULE_SOURCE="${REPO_ROOT}/deployment/udev/99-rock64-stm32-usb.rules"
RULE_TARGET="/etc/udev/rules.d/99-rock64-stm32-usb.rules"
[[ -f "${RULE_SOURCE}" ]] || {
  echo "[auto_device_config] ERROR: missing ${RULE_SOURCE}" >&2
  exit 1
}
install -D -m 0644 "${RULE_SOURCE}" "${RULE_TARGET}"
udevadm control --reload-rules
udevadm trigger --subsystem-match=tty
udevadm settle

CONFIG_DIR="${REPO_ROOT}/deployment/systemd"
CONFIG_FILE="${CONFIG_DIR}/systemd_config.conf"
CONFIG_EXAMPLE="${CONFIG_DIR}/systemd_config.conf.example"
if [[ ! -f "${CONFIG_FILE}" ]]; then
  [[ -f "${CONFIG_EXAMPLE}" ]] || {
    echo "[auto_device_config] ERROR: missing ${CONFIG_EXAMPLE}" >&2
    exit 1
  }
  install -D -m 0644 "${CONFIG_EXAMPLE}" "${CONFIG_FILE}"
fi

backup="${CONFIG_FILE}.backup.$(date +%Y%m%d-%H%M%S)"
cp "${CONFIG_FILE}" "${backup}"
if grep -q '^SERIAL_PORT=' "${CONFIG_FILE}"; then
  sed -i 's|^SERIAL_PORT=.*|SERIAL_PORT=/dev/rock64_stm32|' "${CONFIG_FILE}"
else
  printf '\nSERIAL_PORT=/dev/rock64_stm32\n' >> "${CONFIG_FILE}"
fi

if [[ ! -e /dev/rock64_stm32 ]]; then
  echo "[auto_device_config] ERROR: udev did not create /dev/rock64_stm32." >&2
  echo "[auto_device_config] Candidate was ${wch_devices[0]}; inspect: udevadm info --name ${wch_devices[0]}" >&2
  exit 1
fi

echo "[auto_device_config] WCH motor UART: ${wch_devices[0]} -> /dev/rock64_stm32"
echo "[auto_device_config] Config backup: ${backup}"
if [[ "${RESTART}" == true ]] &&
   command -v systemctl >/dev/null 2>&1 &&
   systemctl cat rock64-robot.service >/dev/null 2>&1; then
  systemctl restart rock64-robot.service
  systemctl is-active --quiet rock64-robot.service
  echo "[auto_device_config] rock64-robot.service restarted."
else
  echo "[auto_device_config] Service not restarted; use --restart after reviewing the link."
fi
