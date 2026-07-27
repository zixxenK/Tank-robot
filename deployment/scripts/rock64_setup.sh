#!/usr/bin/env bash
# rock64_setup.sh — Rock64 Ranger deployment setup & installation script.
#
# Usage:
#   sudo bash rock64_setup.sh [--ros-distro humble|auto]
#                             [--serial-port /dev/ttyUSB0]
#                             [--camera-ip 192.168.1.125]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DEPLOY_DIR="${REPO_ROOT}/deployment"

resolve_host_ws() {
  if [[ -n "${HOST_WS_PATH:-}" ]]; then
    echo "${HOST_WS_PATH}"
    return
  fi

  if [[ -d "${REPO_ROOT}/host_ws/src" ]]; then
    echo "${REPO_ROOT}/host_ws"
    return
  fi

  echo "${REPO_ROOT}/ros2_ws"
}

ROS2_WS="$(resolve_host_ws)"

# ── Defaults ──────────────────────────────────────────────────────────────
ROS_DISTRO_ARG="auto"
SERIAL_PORT="/dev/rock64_stm32"
CAMERA_IP="192.168.1.125"
ROCK64_IP="192.168.1.139"

# ── Parse command-line args ───────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --ros-distro)   ROS_DISTRO_ARG="$2"; shift 2 ;;
    --serial-port)  SERIAL_PORT="$2";    shift 2 ;;
    --camera-ip)    CAMERA_IP="$2";      shift 2 ;;
    --rock64-ip)    ROCK64_IP="$2";      shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

# ── ROS2 distro resolution ────────────────────────────────────────────────
resolve_target_ros_distro() {
  local requested="$1"
  if [[ "${requested}" != "auto" ]]; then
    if [[ "${requested}" != "humble" ]]; then
      echo "[setup] ERROR: Only ROS2 'humble' is supported by this setup script policy." >&2
      return 1
    fi
    echo "${requested}"
    return
  fi
  # Detect Ubuntu version and map to ROS2 distro
  # Auto mode is intentionally Humble-only.
  local ubuntu_version
  ubuntu_version=$(lsb_release -rs 2>/dev/null || echo "0")
  case "${ubuntu_version}" in
    22.*)  echo "humble" ;;
    *)
      echo "[setup] ERROR: Auto ROS distro resolution only supports Ubuntu 22.04 (Humble)." >&2
      return 1
      ;;
  esac
}

RESOLVED_DISTRO="$(resolve_target_ros_distro "${ROS_DISTRO_ARG}")"
echo "[setup] Target ROS2 distro: ${RESOLVED_DISTRO}"
echo "[setup] Host workspace     : ${ROS2_WS}"

UBUNTU_VERSION="$(lsb_release -rs 2>/dev/null || echo "0")"
if [[ ! "${UBUNTU_VERSION}" =~ ^22\. ]]; then
  echo "[setup] ERROR: Ubuntu ${UBUNTU_VERSION} is not supported by this script." >&2
  echo "[setup] Use Ubuntu 22.04 (ROS Humble) on Rock64 for this repository policy." >&2
  echo "[setup] Current board reports Armbian/Ubuntu ${UBUNTU_VERSION}." >&2
  exit 2
fi

# ── Install system dependencies ───────────────────────────────────────────
echo "[setup] Installing system dependencies..."

MICROROS_AGENT_PKG="ros-${RESOLVED_DISTRO}-micro-ros-agent"
if apt-cache show "${MICROROS_AGENT_PKG}" >/dev/null 2>&1; then
  echo "[setup] Found optional package: ${MICROROS_AGENT_PKG}"
else
  echo "[setup] WARNING: ${MICROROS_AGENT_PKG} not available for this architecture/repo; skipping package install."
  MICROROS_AGENT_PKG=""
fi

ROSGZ_PKG="ros-${RESOLVED_DISTRO}-ros-gz"
if apt-cache show "${ROSGZ_PKG}" >/dev/null 2>&1; then
  echo "[setup] Found optional package: ${ROSGZ_PKG}"
else
  echo "[setup] WARNING: ${ROSGZ_PKG} not available; Gazebo Harmonic launch may be unavailable until ros_gz is installed from your apt source."
  ROSGZ_PKG=""
fi

apt-get update -qq
apt-get install -y --no-install-recommends \
  "ros-${RESOLVED_DISTRO}-desktop" \
  ${MICROROS_AGENT_PKG:+"${MICROROS_AGENT_PKG}"} \
  ${ROSGZ_PKG:+"${ROSGZ_PKG}"} \
  "ros-${RESOLVED_DISTRO}-cv-bridge" \
  "ros-${RESOLVED_DISTRO}-rviz2" \
  "ros-${RESOLVED_DISTRO}-visualization-msgs" \
  "ros-${RESOLVED_DISTRO}-rmw-fastrtps-cpp" \
  python3-colcon-common-extensions \
  python3-rosdep \
  python3-pip \
  python3-serial \
  python3-opencv \
  python3-pygame \
  python3-evdev \
  bluez \
  joystick \
  udev \
  gcc-arm-none-eabi \
  libnewlib-arm-none-eabi \
  libstdc++-arm-none-eabi-newlib \
  cmake \
  stlink-tools \
  openocd

if [[ -z "${MICROROS_AGENT_PKG}" ]]; then
  echo "[setup] Adding micro_ros_agent source fallback into workspace..."
  mkdir -p "${ROS2_WS}/src"
  if [[ ! -d "${ROS2_WS}/src/micro_ros_agent/.git" ]]; then
    git clone --depth 1 -b "${RESOLVED_DISTRO}" \
      https://github.com/micro-ROS/micro-ROS-Agent.git \
      "${ROS2_WS}/src/micro_ros_agent"
  else
    echo "[setup] micro_ros_agent source already present — skipping clone."
  fi
fi

# ── Create udev rule for STM32 serial port ────────────────────────────────
echo "[setup] Installing udev rule for STM32 serial port..."
cat > /etc/udev/rules.d/99-rock64-stm32.rules <<'EOF'
# Rock64 Ranger — STM32 motor controller via USB-UART adapter
SUBSYSTEM=="tty", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="5740", \
  SYMLINK+="rock64_stm32", MODE="0666"
EOF
udevadm control --reload-rules

# ── Write deployment config ───────────────────────────────────────────────
echo "[setup] Writing systemd_config.conf..."
cat > "${DEPLOY_DIR}/systemd/systemd_config.conf" <<EOF
# Rock64 Ranger — Deployment Configuration
# Generated by rock64_setup.sh on $(date)

# Network
ROCK64_IP=${ROCK64_IP}

# Hardware
SERIAL_PORT=${SERIAL_PORT}
CAMERA_IP_STATION=${CAMERA_IP}
USE_CAMERA_BRIDGE=false

# ROS
ROS_DISTRO=${RESOLVED_DISTRO}
ROS_DOMAIN_ID=42
RMW_IMPLEMENTATION=rmw_fastrtps_cpp
ROBOT_NAMESPACE=rock64_1
HOST_WS_PATH=${ROS2_WS}
EOF

# ── Build ROS2 workspace ───────────────────────────────────────────────────
echo "[setup] Building ROS2 workspace..."
# shellcheck source=/dev/null
source "/opt/ros/${RESOLVED_DISTRO}/setup.bash"
cd "${ROS2_WS}"
colcon build --symlink-install

# ── Install systemd service ────────────────────────────────────────────────
echo "[setup] Installing systemd service..."
bash "${DEPLOY_DIR}/scripts/apply_systemd.sh"

echo "[setup] Setup complete! Reboot or run: sudo systemctl start rock64-robot.service"
