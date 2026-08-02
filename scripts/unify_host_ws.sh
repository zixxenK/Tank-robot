#!/usr/bin/env bash
# One-shot host workspace unify/build/launch helper for Ubuntu 22.04 + ROS2 Humble.
set -euo pipefail

MODE="sim"
TELEOP_MODE="keyboard"
INSTALL_DEPS=1
BUILD_PKGS="robot_bringup robot_drivers robot_teleop"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="$2"
      shift 2
      ;;
    --teleop)
      TELEOP_MODE="$2"
      shift 2
      ;;
    --no-install-deps)
      INSTALL_DEPS=0
      shift
      ;;
    --help|-h)
      cat <<'USAGE'
Usage: bash scripts/unify_host_ws.sh [--mode sim|hardware|teleop] [--teleop keyboard|ps5] [--no-install-deps]

Default behavior:
  1) Validates Ubuntu 22.04 + ROS2 Humble runtime policy.
  2) Installs missing runtime deps for Gazebo/RViz (if sudo is available).
  3) Rebuilds host workspace packages.
  4) Verifies installed launch files.
  5) Launches selected mode.
USAGE
      exit 0
      ;;
    *)
      echo "[unify] Unknown option: $1" >&2
      exit 2
      ;;
  esac
done

if [[ "$MODE" != "sim" && "$MODE" != "hardware" && "$MODE" != "teleop" ]]; then
  echo "[unify] Invalid mode '$MODE'. Use sim, hardware, or teleop." >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

resolve_host_ws() {
  if [[ -n "${HOST_WS_PATH:-}" && -d "${HOST_WS_PATH}/src" ]]; then
    echo "${HOST_WS_PATH}"
    return
  fi
  if [[ -d "${REPO_ROOT}/host_ws/src" ]]; then
    echo "${REPO_ROOT}/host_ws"
    return
  fi
  echo "[unify] ERROR: host_ws/src not found" >&2
  return 1
}

HOST_WS="$(resolve_host_ws)"

# Ensure standard Linux binary paths are present even if shell overlays mutate PATH.
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"

if [[ ! -f /opt/ros/humble/setup.bash ]]; then
  echo "[unify] ROS2 humble not found at /opt/ros/humble/setup.bash" >&2
  echo "[unify] Install ROS2 Humble first, then re-run." >&2
  exit 3
fi

UBUNTU_VERSION="$(lsb_release -rs 2>/dev/null || echo "0")"
if [[ ! "$UBUNTU_VERSION" =~ ^22\. ]]; then
  echo "[unify] WARNING: Ubuntu ${UBUNTU_VERSION} detected. Repository policy targets Ubuntu 22.04 + Humble." >&2
fi

install_deps_if_needed() {
  local pkgs=(
    ros-humble-rviz2
    ros-humble-visualization-msgs
    ros-humble-ros-gz
    ros-humble-ros-gz-bridge
    ros-humble-ros-gz-sim
  )

  local missing=()
  is_pkg_installed() {
    local pkg_name="$1"
    dpkg -l "$pkg_name" 2>/dev/null | awk 'NR > 5 && $1 == "ii" { found = 1 } END { exit(found ? 0 : 1) }'
  }

  for pkg in "${pkgs[@]}"; do
    if ! is_pkg_installed "$pkg"; then
      missing+=("$pkg")
    fi
  done

  if [[ ${#missing[@]} -eq 0 ]]; then
    echo "[unify] Runtime dependencies already installed."
    return
  fi

  if [[ "$INSTALL_DEPS" -eq 0 ]]; then
    echo "[unify] Missing deps: ${missing[*]}" >&2
    echo "[unify] Re-run without --no-install-deps or install manually with apt." >&2
    exit 4
  fi

  if ! command -v sudo >/dev/null 2>&1; then
    echo "[unify] sudo not found. Install manually:" >&2
    echo "sudo apt-get update && sudo apt-get install -y ${missing[*]}" >&2
    exit 4
  fi

  wait_for_apt_locks() {
    local lock_files=(
      /var/lib/dpkg/lock-frontend
      /var/lib/dpkg/lock
      /var/cache/apt/archives/lock
      /var/lib/apt/lists/lock
    )
    local waited=0
    local max_wait=300

    while true; do
      local locked=0
      for lock_file in "${lock_files[@]}"; do
        if sudo fuser "$lock_file" >/dev/null 2>&1; then
          locked=1
          break
        fi
      done

      if [[ "$locked" -eq 0 ]]; then
        break
      fi

      if [[ "$waited" -ge "$max_wait" ]]; then
        echo "[unify] ERROR: apt/dpkg lock held for more than ${max_wait}s." >&2
        echo "[unify] Re-run after unattended upgrades finish." >&2
        exit 7
      fi

      if (( waited % 30 == 0 )); then
        echo "[unify] Waiting for apt/dpkg lock to clear... (${waited}s)"
      fi
      sleep 3
      waited=$((waited + 3))
    done
  }

  echo "[unify] Installing missing deps: ${missing[*]}"
  wait_for_apt_locks
  sudo apt-get update
  wait_for_apt_locks
  sudo apt-get install -y "${missing[@]}"
}

# ROS setup scripts may read optional vars that are unset under nounset.
set +u
source /opt/ros/humble/setup.bash
set -u

if [[ "$MODE" == "sim" ]]; then
  install_deps_if_needed
fi

echo "[unify] Host workspace: ${HOST_WS}"
cd "${HOST_WS}"

colcon build --symlink-install --packages-up-to ${BUILD_PKGS}
set +u
source install/setup.bash
set -u

if [[ ! -f install/robot_bringup/share/robot_bringup/launch/gazebo_telemetry.launch.py ]]; then
  echo "[unify] ERROR: gazebo_telemetry.launch.py not installed." >&2
  echo "[unify] Try: colcon build --symlink-install --packages-select robot_bringup --cmake-clean-cache" >&2
  exit 5
fi

if [[ "$MODE" == "sim" ]]; then
  GZ_SIM_EXEC=""
  GZ_SIM_SUBCOMMAND=""
  if command -v gz >/dev/null 2>&1; then
    GZ_SIM_EXEC="$(command -v gz)"
    GZ_SIM_SUBCOMMAND="sim"
  elif [[ -x /usr/bin/gz ]]; then
    GZ_SIM_EXEC="/usr/bin/gz"
    GZ_SIM_SUBCOMMAND="sim"
  elif command -v ign >/dev/null 2>&1; then
    GZ_SIM_EXEC="$(command -v ign)"
    GZ_SIM_SUBCOMMAND="gazebo"
  elif [[ -x /usr/bin/ign ]]; then
    GZ_SIM_EXEC="/usr/bin/ign"
    GZ_SIM_SUBCOMMAND="gazebo"
  fi

  if [[ -z "$GZ_SIM_EXEC" ]]; then
    echo "[unify] ERROR: neither 'gz' nor 'ign' CLI was found after dependency install." >&2
    echo "[unify] Verify ros-gz packages and Gazebo tooling are available for your apt sources." >&2
    exit 6
  fi
  if ! ros2 pkg prefix ros_gz_bridge >/dev/null 2>&1; then
    echo "[unify] ERROR: ros_gz_bridge package not found in current ROS environment." >&2
    exit 6
  fi
  export GZ_SIM_EXEC
  export GZ_SIM_SUBCOMMAND
  echo "[unify] Using Gazebo executable: ${GZ_SIM_EXEC} ${GZ_SIM_SUBCOMMAND}"
  echo "[unify] Launching Gazebo telemetry stack..."
  exec ros2 launch robot_bringup gazebo_telemetry.launch.py
elif [[ "$MODE" == "hardware" ]]; then
  echo "[unify] Launching hardware bringup stack..."
  _SERIAL="${SERIAL_PORT:-/dev/rock64_stm32}"
  exec ros2 launch robot_bringup rock64_bringup.launch.py \
    use_hardware_bridge:=true \
    serial_port:="${_SERIAL}"
else
  case "$TELEOP_MODE" in
    keyboard)
      echo "[unify] Launching keyboard teleop..."
      exec ros2 run robot_teleop keyboard_teleop
      ;;
    ps5)
      echo "[unify] Launching PS5 teleop bridge..."
      exec ros2 run robot_teleop ps5_ros_bridge
      ;;
    *)
      echo "[unify] Invalid teleop mode '$TELEOP_MODE'. Use keyboard or ps5." >&2
      exit 2
      ;;
  esac
fi
