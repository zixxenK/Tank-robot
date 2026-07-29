#!/usr/bin/env bash
# rebuild_robot_bringup.sh - Rebuild only robot_bringup package
# Run this to fix the launch file import issue without rebuilding everything

set -eo pipefail  # Removed -u to allow undefined variables

echo "=========================================="
echo "Rebuild robot_bringup Package Only"
echo "=========================================="

REPO_ROOT="${REPO_ROOT:-/opt/rock64-robot}"
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
echo "Step 2: Rebuild only robot_bringup package..."
echo "----------------------------------------------"
cd "${WS_PATH}"
colcon build --packages-select robot_bringup --symlink-install

echo ""
echo "Step 3: Restart systemd service..."
echo "----------------------------------------------"
systemctl restart rock64-robot.service

echo ""
echo "Step 4: Check service status..."
echo "----------------------------------------------"
sleep 3
systemctl status rock64-robot.service --no-pager

echo ""
echo "Step 5: Check if nodes are running..."
echo "----------------------------------------------"
sleep 2
source install/setup.bash
ros2 node list
ros2 topic list

echo ""
echo "=========================================="
echo "Rebuild Complete"
echo "=========================================="
