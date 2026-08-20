#!/usr/bin/env bash
# Optional deterministic Fast DDS discovery server for WSL2/NAT networks.
set -Eeuo pipefail

SERVER_ID="${FASTDDS_DISCOVERY_SERVER_ID:-0}"
PORT="${FASTDDS_DISCOVERY_PORT:-11811}"

command -v fastdds >/dev/null 2>&1 || {
  echo "fastdds CLI is missing; install the ROS 2 Fast DDS tools first." >&2
  exit 1
}

echo "Starting Fast DDS discovery server id=${SERVER_ID} port=${PORT}"
exec fastdds discovery -i "${SERVER_ID}" -p "${PORT}"
