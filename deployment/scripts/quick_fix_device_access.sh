#!/usr/bin/env bash
# Repair the canonical Rock64 udev/config path without overwriting operator
# network or accessory settings. No firmware, service, or motor command is
# started unless --restart is explicitly requested.
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
      echo "Installs canonical udev rules and preserves existing deployment config."
      exit 0
      ;;
    *) echo "[quick_fix_device_access] ERROR: unknown option: $1" >&2; exit 2 ;;
  esac
done

if [[ "$(id -u)" -ne 0 ]]; then
  echo "[quick_fix_device_access] ERROR: run as root: sudo bash $0" >&2
  exit 1
fi

UDEV_DIR="${REPO_ROOT}/deployment/udev"
CONFIG_DIR="${REPO_ROOT}/deployment/systemd"
CONFIG_FILE="${CONFIG_DIR}/systemd_config.conf"
CONFIG_EXAMPLE="${CONFIG_DIR}/systemd_config.conf.example"

for rule in 99-rock64-stm32-usb.rules 99-rock64-ps5.rules; do
  [[ -f "${UDEV_DIR}/${rule}" ]] || {
    echo "[quick_fix_device_access] ERROR: missing ${UDEV_DIR}/${rule}" >&2
    exit 1
  }
  install -D -m 0644 "${UDEV_DIR}/${rule}" "/etc/udev/rules.d/${rule}"
done
udevadm control --reload-rules
udevadm trigger --subsystem-match=tty --subsystem-match=input
udevadm settle

if [[ ! -f "${CONFIG_FILE}" ]]; then
  [[ -f "${CONFIG_EXAMPLE}" ]] || {
    echo "[quick_fix_device_access] ERROR: ${CONFIG_EXAMPLE} is missing" >&2
    exit 1
  }
  install -D -m 0644 "${CONFIG_EXAMPLE}" "${CONFIG_FILE}"
fi

config_backup="${CONFIG_FILE}.backup.$(date +%Y%m%d-%H%M%S)"
cp "${CONFIG_FILE}" "${config_backup}"
if grep -q '^SERIAL_PORT=' "${CONFIG_FILE}"; then
  sed -i 's|^SERIAL_PORT=.*|SERIAL_PORT=/dev/rock64_stm32|' "${CONFIG_FILE}"
else
  printf '\nSERIAL_PORT=/dev/rock64_stm32\n' >> "${CONFIG_FILE}"
fi

echo "[quick_fix_device_access] Canonical WCH rule installed for UART1/USART1 PA9-PA10."
echo "[quick_fix_device_access] Canonical PS5 rule installed."
echo "[quick_fix_device_access] Config preserved; backup: ${config_backup}"
if [[ -e /dev/rock64_stm32 ]]; then
  ls -l /dev/rock64_stm32
else
  echo "[quick_fix_device_access] WCH device not present yet; connect the motor UART1 cable."
fi

if [[ "${RESTART}" == true && -e /dev/rock64_stm32 ]] &&
   command -v systemctl >/dev/null 2>&1 &&
   systemctl cat rock64-robot.service >/dev/null 2>&1; then
  systemctl daemon-reload
  systemctl restart rock64-robot.service
  systemctl is-active --quiet rock64-robot.service
  echo "[quick_fix_device_access] rock64-robot.service restarted."
else
  echo "[quick_fix_device_access] Service not restarted. Use --restart after reviewing the device/config state."
fi

echo "[quick_fix_device_access] Follow docs/OPERATOR_GUIDE.md for acceptance and driving."
