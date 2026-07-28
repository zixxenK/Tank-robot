#!/usr/bin/env bash
# fix_ros2_environment.sh - Ensure ROS2 is properly installed and configured
# Run this to fix ROS2 environment issues on the Rock64

set -euo pipefail

echo "=========================================="
echo "ROS2 Environment Fix"
echo "=========================================="

# Detect if running as root for installation
if [[ "$(id -u)" -eq 0 ]]; then
    echo "Running as root - will install ROS2 if needed"
    AS_ROOT=true
else
    echo "Running as regular user - will check environment only"
    AS_ROOT=false
fi

REPO_ROOT="${REPO_ROOT:-/opt/rock64-robot}"
cd "${REPO_ROOT}" || exit 1

echo ""
echo "Step 1: Check ROS2 installation..."
echo "----------------------------------------------"

if [[ ! -d /opt/ros/humble ]]; then
    echo "❌ ROS2 Humble not found in /opt/ros/humble"
    
    if [[ "$AS_ROOT" == true ]]; then
        echo "Installing ROS2 Humble..."
        
        # Add ROS2 apt repository
        apt install -y software-properties-common
        add-apt-repository universe
        apt update && apt install -y curl gnupg lsb-release
        
        # Add ROS2 GPG key
        curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | tee /etc/apt/sources.list.d/ros2.list > /dev/null
        
        # Install ROS2 Humble
        apt update
        apt install -y ros-humble-desktop python3-rosdep2
        
        # Initialize rosdep
        rosdep init
        rosdep update
        
        echo "✅ ROS2 Humble installed"
    else
        echo "Please run this script with sudo to install ROS2"
        exit 1
    fi
else
    echo "✅ ROS2 Humble found at /opt/ros/humble"
fi

echo ""
echo "Step 2: Check workspace build status..."
echo "----------------------------------------------"

WS_PATH="${REPO_ROOT}/host_ws"
if [[ ! -d "${WS_PATH}" ]]; then
    echo "❌ host_ws not found, checking for ros2_ws"
    WS_PATH="${REPO_ROOT}/ros2_ws"
fi

if [[ -d "${WS_PATH}" ]]; then
    echo "Found workspace at: ${WS_PATH}"
    
    if [[ ! -f "${WS_PATH}/install/setup.bash" ]]; then
        echo "❌ Workspace not built (install/setup.bash missing)"
        echo "Building workspace..."
        
        # Source ROS2
        source /opt/ros/humble/setup.bash
        
        # Install dependencies
        if [[ -f "${WS_PATH}/src/dependencies.txt" ]]; then
            rosdep install --from-paths src --ignore-src -r -y
        fi
        
        # Build workspace
        cd "${WS_PATH}"
        colcon build --symlink-install
        
        echo "✅ Workspace built"
    else
        echo "✅ Workspace already built"
    fi
else
    echo "❌ No workspace found"
    exit 1
fi

echo ""
echo "Step 3: Update robot_start.sh to ensure proper environment..."
echo "----------------------------------------------"

START_SCRIPT="${REPO_ROOT}/deployment/scripts/robot_start.sh"
SOURCE_SCRIPT="${REPO_ROOT}/deployment/scripts/source_ros2_ws.sh"

# Ensure source_ros2_ws.sh exists and is correct
if [[ ! -f "${SOURCE_SCRIPT}" ]]; then
    echo "Creating source_ros2_ws.sh..."
    cat > "${SOURCE_SCRIPT}" <<'EOF'
#!/usr/bin/env bash
# source_ros2_ws.sh - Source ROS2 workspace with proper error handling

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${DEPLOY_DIR}/.." && pwd)"

# Load deployment config
CONFIG_FILE="${DEPLOY_DIR}/systemd/systemd_config.conf"
if [[ -f "${CONFIG_FILE}" ]]; then
    source "${CONFIG_FILE}"
fi

# Set ROS_DISTRO if not configured
ROS_DISTRO="${ROS_DISTRO:-humble}"

# Source ROS2 environment
if [[ -f "/opt/ros/${ROS_DISTRO}/setup.bash" ]]; then
    source "/opt/ros/${ROS_DISTRO}/setup.bash"
else
    echo "[source_ros2_ws] ERROR: ROS2 ${ROS_DISTRO} not found at /opt/ros/${ROS_DISTRO}/setup.bash"
    exit 1
fi

# Resolve and source workspace
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

HOST_WS="$(resolve_host_ws)"

if [[ -f "${HOST_WS}/install/setup.bash" ]]; then
    source "${HOST_WS}/install/setup.bash"
    echo "[source_ros2_ws] Sourced workspace: ${HOST_WS}"
else
    echo "[source_ros2_ws] WARNING: Workspace not built at ${HOST_WS}"
    echo "[source_ros2_ws] Sourcing ROS2 base environment only"
fi

# Export ROS2 environment variables
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"
export ROBOT_NAMESPACE="${ROBOT_NAMESPACE:-rock64_1}"
EOF
    chmod +x "${SOURCE_SCRIPT}"
    echo "✅ Created source_ros2_ws.sh"
fi

echo ""
echo "Step 4: Test ROS2 environment..."
echo "----------------------------------------------"

# Source ROS2 to test
source /opt/ros/humble/setup.bash
if [[ -f "${WS_PATH}/install/setup.bash" ]]; then
    source "${WS_PATH}/install/setup.bash"
fi

if command -v ros2 &>/dev/null; then
    echo "✅ ROS2 command available"
    echo "ROS2 version: $(ros2 --version)"
    echo "ROS_DISTRO: ${ROS_DISTRO}"
else
    echo "❌ ROS2 command still not available"
    exit 1
fi

echo ""
echo "Step 5: Restart systemd service with new environment..."
echo "----------------------------------------------"

if [[ "$AS_ROOT" == true ]]; then
    systemctl daemon-reload
    systemctl restart rock64-robot.service
    echo "✅ Systemd service restarted"
    
    echo ""
    echo "Checking service status..."
    sleep 2
    systemctl status rock64-robot.service --no-pager || true
else
    echo "Run 'sudo systemctl restart rock64-robot.service' to restart the service"
fi

echo ""
echo "=========================================="
echo "ROS2 Environment Fix Complete"
echo "=========================================="
echo ""
echo "You can now test ROS2 manually:"
echo "  source /opt/ros/humble/setup.bash"
echo "  source ${WS_PATH}/install/setup.bash"
echo "  ros2 launch robot_bringup rock64_bringup.launch.py"
