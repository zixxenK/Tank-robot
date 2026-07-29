#!/usr/bin/env bash
# quick_rebuild.sh - Quick rebuild of robot_bringup package only
# Run this after launch file changes

set -eo pipefail

echo "=========================================="
echo "Quick Rebuild - robot_bringup Package"
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
echo "Step 2: Rebuild robot_bringup package only..."
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
echo "=========================================="
echo "Quick Rebuild Complete"
echo "=========================================="
