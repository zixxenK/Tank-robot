#!/usr/bin/env bash
# apply_systemd.sh — Install and enable the rock64-robot systemd service.
#
# Must be run as root (sudo).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
SERVICE_SRC="${DEPLOY_DIR}/systemd/rock64-robot.service"
SERVICE_DST="/etc/systemd/system/rock64-robot.service"
CONFIG_SRC="${DEPLOY_DIR}/systemd/systemd_config.conf"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "[apply_systemd] ERROR: Must be run as root (sudo)" >&2
  exit 1
fi

# ── Copy systemd service file ─────────────────────────────────────────────
echo "[apply_systemd] Copying service file to ${SERVICE_DST}..."
cp "${SERVICE_SRC}" "${SERVICE_DST}"

# ── Embed configuration values into the service environment ───────────────
if [[ -f "${CONFIG_SRC}" ]]; then
  echo "[apply_systemd] Loading config from ${CONFIG_SRC}"
  # Create EnvironmentFile entry pointing to the config
  sed -i "s|^EnvironmentFile=.*|EnvironmentFile=${CONFIG_SRC}|" "${SERVICE_DST}"
else
  echo "[apply_systemd] WARNING: ${CONFIG_SRC} not found. Run rock64_setup.sh first."
fi

# ── Enable and start service ──────────────────────────────────────────────
systemctl daemon-reload
systemctl enable rock64-robot.service
systemctl start  rock64-robot.service

echo "[apply_systemd] Service installed and started."
systemctl status rock64-robot.service --no-pager || true
