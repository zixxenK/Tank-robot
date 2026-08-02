#!/usr/bin/env bash
# check_ros_nodes.sh - Check if ROS2 nodes are running properly
# Run this to verify the ROS2 system state

set -eo pipefail  # Removed -u to allow undefined variables

echo "=========================================="
echo "ROS2 Node Status Check"
echo "=========================================="

# Source ROS2 environment
source /opt/ros/humble/setup.bash
source /opt/rock64-robot/host_ws/install/setup.bash

echo ""
echo "Step 1: Check ROS2 nodes..."
echo "----------------------------------------------"
ros2 node list 2>/dev/null || echo "No ROS2 nodes found or ROS2 daemon not running"

echo ""
echo "Step 2: Check ROS2 topics..."
echo "----------------------------------------------"
ros2 topic list 2>/dev/null || echo "No ROS2 topics found"

echo ""
echo "Step 3: Check for bridge alive topic..."
echo "----------------------------------------------"
if ros2 topic list 2>/dev/null | grep -q "/stm32/bridge_alive"; then
    echo "✅ /stm32/bridge_alive topic found"
    echo "Current state:"
    timeout 5 ros2 topic echo /stm32/bridge_alive --once 2>/dev/null || echo "No data received"
else
    echo "❌ /stm32/bridge_alive topic not found"
fi

echo ""
echo "Step 4: Check systemd service status..."
echo "----------------------------------------------"
sudo systemctl status rock64-robot.service --no-pager || true

echo ""
echo "Step 5: Check recent service logs..."
echo "----------------------------------------------"
sudo journalctl -u rock64-robot.service -n 30 --no-pager

echo ""
echo "=========================================="
echo "Status Check Complete"
echo "=========================================="
