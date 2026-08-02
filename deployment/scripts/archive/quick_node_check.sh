#!/usr/bin/env bash
# quick_node_check.sh - Quick node status check for debugging
# Run this on Rock64 to see why bridges aren't starting

set -eo pipefail

echo "=========================================="
echo "Quick Node Status Check"
echo "=========================================="

REPO_ROOT="${REPO_ROOT:-/opt/rock64-robot}"
cd "${REPO_ROOT}" || exit 1

# Source ROS2
source /opt/ros/humble/setup.bash
source host_ws/install/setup.bash

echo ""
echo "Current ROS2 Environment:"
echo "---------------------------"
echo "ROS_DOMAIN_ID: ${ROS_DOMAIN_ID:-not set}"
echo "RMW_IMPLEMENTATION: ${RMW_IMPLEMENTATION:-not set}"
echo "ROS_LOCALHOST_ONLY: ${ROS_LOCALHOST_ONLY:-not set}"

echo ""
echo "Running Nodes:"
echo "---------------"
ros2 node list 2>/dev/null || echo "No nodes found"

echo ""
echo "Available Topics:"
echo "------------------"
ros2 topic list 2>/dev/null || echo "No topics found"

echo ""
echo "Service Status:"
echo "---------------"
systemctl status rock64-robot.service --no-pager | head -15

echo ""
echo "Recent Service Logs (last 15 lines):"
echo "-------------------------------------"
journalctl -u rock64-robot.service -n 15 --no-pager | tail -15

echo ""
echo "Device Status:"
echo "---------------"
if [[ -e /dev/rock64_stm32 ]]; then
    echo "✅ /dev/rock64_stm32 exists -> $(readlink /dev/rock64_stm32)"
else
    echo "❌ /dev/rock64_stm32 not found"
    echo "Available devices:"
    ls -la /dev/ttyACM* 2>/dev/null || echo "No ACM devices"
fi

echo ""
echo "Launch File Process:"
echo "--------------------"
# Check if ros2 launch process is running
PGID=$(pgrep -f "ros2 launch robot_bringup")
if [[ -n "$PGID" ]]; then
    echo "✅ ROS2 launch process running (PID: $PGID)"
    ps aux | grep -E "ros2 launch|robot_bringup" | grep -v grep
else
    echo "❌ ROS2 launch process not found"
fi

echo ""
echo "=========================================="
echo "Quick Check Complete"
echo "=========================================="
