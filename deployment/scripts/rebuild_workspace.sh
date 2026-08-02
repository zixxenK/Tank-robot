#!/usr/bin/env bash
# rebuild_workspace.sh - Rebuild the ROS2 workspace to fix Python module issues
# Run this to rebuild the workspace after changes

set -eo pipefail  # Removed -u to allow undefined variables

echo "=========================================="
echo "ROS2 Workspace Rebuild"
echo "=========================================="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
cd "${REPO_ROOT}" || exit 1

WS_PATH="${REPO_ROOT}/host_ws"
if [[ ! -d "${WS_PATH}" ]]; then
    echo "❌ Workspace not found at ${WS_PATH}"
    exit 1
fi

echo ""
echo "Step 1: Source ROS2 environment..."
echo "----------------------------------------------"
source /opt/ros/humble/setup.bash

echo ""
echo "Step 2: Clean previous build..."
echo "----------------------------------------------"
cd "${WS_PATH}"
rm -rf build install log

echo ""
echo "Step 3: Install dependencies..."
echo "----------------------------------------------"
rosdep install --from-paths src --ignore-src -r -y

echo ""
echo "Step 4: Build workspace..."
echo "----------------------------------------------"
colcon build --symlink-install

echo ""
echo "Step 5: Verify build..."
echo "----------------------------------------------"
if [[ -f "install/setup.bash" ]]; then
    echo "✅ Workspace built successfully"
    source install/setup.bash
else
    echo "❌ Build failed - setup.bash not found"
    exit 1
fi

echo ""
echo "Step 6: Test Python imports..."
echo "----------------------------------------------"
cd "${WS_PATH}/src/robot_bringup/launch"
python3 -c "import preflight_check; print('✅ preflight_check module imports successfully')"

echo ""
echo "=========================================="
echo "Workspace Rebuild Complete"
echo "=========================================="
echo ""
echo "Restart the systemd service:"
echo "  sudo systemctl restart rock64-robot.service"
