#!/usr/bin/env bash
# apply_systemd.sh — Install and enable the rock64-robot systemd service.
#
# Must be run as root (sudo).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${DEPLOY_DIR}/.." && pwd)"
SERVICE_SRC="${DEPLOY_DIR}/systemd/rock64-robot.service"
SERVICE_DST="/etc/systemd/system/rock64-robot.service"
UPDATE_SERVICE_SRC="${DEPLOY_DIR}/systemd/rock64-robot-update.service"
UPDATE_SERVICE_DST="/etc/systemd/system/rock64-robot-update.service"
UPDATE_TIMER_SRC="${DEPLOY_DIR}/systemd/rock64-robot-update.timer"
UPDATE_TIMER_DST="/etc/systemd/system/rock64-robot-update.timer"
DISCOVERY_SERVICE_SRC="${DEPLOY_DIR}/systemd/rock64-fastdds-discovery.service"
DISCOVERY_SERVICE_DST="/etc/systemd/system/rock64-fastdds-discovery.service"
CONFIG_SRC="${DEPLOY_DIR}/systemd/systemd_config.conf"
ROCK64_SELF_UPDATE_ENABLED="false"

discovery_enabled() {
  [[ "${ROCK64_USE_DISCOVERY_SERVER:-0}" == "1" ||
     "${ROCK64_USE_DISCOVERY_SERVER:-0}" == "true" ]]
}

if [[ -f "${CONFIG_SRC}" ]]; then
  # shellcheck disable=SC1090
  source "${CONFIG_SRC}"
fi

if [[ "$(id -u)" -ne 0 ]]; then
  echo "[apply_systemd] ERROR: Must be run as root (sudo)" >&2
  exit 1
fi

# ── Copy systemd service file ─────────────────────────────────────────────
echo "[apply_systemd] Copying service file to ${SERVICE_DST}..."
cp "${SERVICE_SRC}" "${SERVICE_DST}"
echo "[apply_systemd] Copying update units..."
cp "${UPDATE_SERVICE_SRC}" "${UPDATE_SERVICE_DST}"
cp "${UPDATE_TIMER_SRC}" "${UPDATE_TIMER_DST}"
# ── Install udev rules ───────────────────────────────────────────────────
if [[ -d "${DEPLOY_DIR}/udev" ]]; then
  echo "[apply_systemd] Installing udev rules..."
  cp "${DEPLOY_DIR}/udev/"*.rules /etc/udev/rules.d/ 2>/dev/null || true
  udevadm control --reload-rules || true
  udevadm trigger || true
fi

sed -i "s|^WorkingDirectory=.*|WorkingDirectory=${REPO_ROOT}|" "${SERVICE_DST}"
sed -i "s|^ExecStart=.*|ExecStart=/bin/bash ${REPO_ROOT}/deployment/scripts/robot_start.sh|" "${SERVICE_DST}"
sed -i "s|^WorkingDirectory=.*|WorkingDirectory=${REPO_ROOT}|" "${UPDATE_SERVICE_DST}"
sed -i "s|^ExecStart=.*|ExecStart=/bin/bash ${REPO_ROOT}/deployment/scripts/self_update.sh|" "${UPDATE_SERVICE_DST}"
if [[ -f "${DISCOVERY_SERVICE_DST}" ]]; then
  sed -i "s|^EnvironmentFile=.*|EnvironmentFile=${CONFIG_SRC}|" "${DISCOVERY_SERVICE_DST}"
fi

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
if [[ "${ROCK64_SELF_UPDATE_ENABLED:-false}" == "true" ]]; then
  systemctl enable --now rock64-robot-update.timer
  echo "[apply_systemd] Git self-update timer enabled."
else
  systemctl disable --now rock64-robot-update.timer 2>/dev/null || true
  echo "[apply_systemd] Git self-update timer disabled; use the local PC deployment workflow."
fi
if discovery_enabled; then
  if ! command -v fastdds >/dev/null 2>&1; then
    echo "[apply_systemd] ERROR: ROCK64_USE_DISCOVERY_SERVER is enabled but fastdds is not installed." >&2
    exit 1
  fi
  if [[ ! -f "${DISCOVERY_SERVICE_SRC}" ]]; then
    echo "[apply_systemd] ERROR: discovery service source is missing." >&2
    exit 1
  fi
  echo "[apply_systemd] Installing Fast DDS discovery service..."
  cp "${DISCOVERY_SERVICE_SRC}" "${DISCOVERY_SERVICE_DST}"
  systemctl enable --now rock64-fastdds-discovery.service
else
  systemctl disable --now rock64-fastdds-discovery.service 2>/dev/null || true
  echo "[apply_systemd] Fast DDS discovery server disabled; using normal DDS discovery."
fi
if systemctl is-active --quiet rock64-robot.service; then
  # A source sync can rebuild the workspace while the old process is still
  # running.  Starting an already-active unit is a no-op, so explicitly
  # restart it to make the deployed commit the running commit.
  systemctl restart rock64-robot.service
else
  systemctl start rock64-robot.service
fi

echo "[apply_systemd] Service installed and started."
systemctl status rock64-robot.service --no-pager || true
