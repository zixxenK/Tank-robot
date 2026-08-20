#!/usr/bin/env bash
# rock64_setup.sh — Rock64 Ranger deployment setup & installation script.
#
# Usage:
#   sudo bash rock64_setup.sh [--ros-distro humble|auto]
#                             [--serial-port /dev/rock64_stm32]
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

  echo "[setup] ERROR: host_ws/src not found" >&2
  return 1
}

HOST_WS="$(resolve_host_ws)"

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
echo "[setup] Host workspace     : ${HOST_WS}"

UBUNTU_VERSION="$(lsb_release -rs 2>/dev/null || echo "0")"
if [[ ! "${UBUNTU_VERSION}" =~ ^22\. ]]; then
  echo "[setup] ERROR: Ubuntu ${UBUNTU_VERSION} is not supported by this script." >&2
  echo "[setup] Use Ubuntu 22.04 (ROS Humble) on Rock64 for this repository policy." >&2
  echo "[setup] Current board reports Armbian/Ubuntu ${UBUNTU_VERSION}." >&2
  exit 2
fi

# ── Install system dependencies ───────────────────────────────────────────
echo "[setup] Installing system dependencies..."

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
  ${ROSGZ_PKG:+"${ROSGZ_PKG}"} \
  "ros-${RESOLVED_DISTRO}-cv-bridge" \
  "ros-${RESOLVED_DISTRO}-rviz2" \
  "ros-${RESOLVED_DISTRO}-slam-toolbox" \
  "ros-${RESOLVED_DISTRO}-navigation2" \
  "ros-${RESOLVED_DISTRO}-nav2-bringup" \
  "ros-${RESOLVED_DISTRO}-rosbridge-server" \
  "ros-${RESOLVED_DISTRO}-visualization-msgs" \
  "ros-${RESOLVED_DISTRO}-rmw-fastrtps-cpp" \
  python3-colcon-common-extensions \
  python3-rosdep \
  python3-pip \
  python3-serial \
  python3-libgpiod \
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

# ── Create udev rules for STM32 and PS5 controller ────────────────────────
echo "[setup] Installing udev rules..."
cat > /etc/udev/rules.d/99-rock64-stm32.rules <<'EOF'
# Rock64 Ranger — Hiwonder WCH USB-UART (1a86:55d4) to USART1 PA9/PA10
# (product connector labeled UART1).
# Creates a stable alias to the underlying /dev/ttyACM* node.
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="55d4", \
  SYMLINK+="rock64_stm32", SYMLINK+="rock64_stm32_wch", GROUP="dialout", MODE="0664", \
  ENV{ID_MM_PORT_IGNORE}="1"
EOF

cat > /etc/udev/rules.d/99-rock64-ps5.rules <<'EOF'
# Sony DualSense (PS5) Wireless Controller — USB link
KERNEL=="js[0-9]*", ATTRS{idVendor}=="054c", ATTRS{idProduct}=="0ce6", MODE="0666", GROUP="input", SYMLINK+="input/ps5_controller", SYMLINK+="input/ps5_controller_js"
# Sony DualSense (PS5) Wireless Controller — Bluetooth link
KERNEL=="js[0-9]*", KERNELS=="*054C:0CE6*", MODE="0666", GROUP="input", SYMLINK+="input/ps5_controller", SYMLINK+="input/ps5_controller_js"
# General joystick device permissions: allow non-root operator reading
KERNEL=="js[0-9]*", SUBSYSTEM=="input", MODE="0666", GROUP="input"
KERNEL=="event[0-9]*", SUBSYSTEM=="input", MODE="0666", GROUP="input"
EOF

udevadm control --reload-rules
udevadm trigger

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
USE_AUDIO=true

# Direct LiDAR acquisition
USE_LIDAR=true
LIDAR_SERIAL_PORT=/dev/ttyS2
LIDAR_SYNC_GPIOCHIP=/dev/gpiochip2

# Canonical packed-binary STM32 bridge
USE_HARDWARE_BRIDGE=true

# ROS
ROS_DISTRO=${RESOLVED_DISTRO}
ROS_DOMAIN_ID=42
RMW_IMPLEMENTATION=rmw_fastrtps_cpp
ROBOT_NAMESPACE=rock64_1
HOST_WS_PATH=${HOST_WS}
EOF

# ── Build ROS2 workspace ───────────────────────────────────────────────────
echo "[setup] Building ROS2 workspace..."
# shellcheck source=/dev/null
source "/opt/ros/${RESOLVED_DISTRO}/setup.bash"
cd "${HOST_WS}"
colcon build --symlink-install

# ── Install systemd service ────────────────────────────────────────────────
echo "[setup] Installing systemd service..."
bash "${DEPLOY_DIR}/scripts/apply_systemd.sh"

echo "[setup] Setup complete! Reboot or run: sudo systemctl start rock64-robot.service"
