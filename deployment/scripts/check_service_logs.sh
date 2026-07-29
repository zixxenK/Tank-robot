#!/usr/bin/env bash
# check_service_logs.sh - Detailed service log analysis
# Run this to see why nodes aren't starting despite service being active

set -eo pipefail  # Removed -u to allow undefined variables

echo "=========================================="
echo "Service Log Analysis"
echo "=========================================="

echo ""
echo "Step 1: Current Service Status"
echo "----------------------------------------------"
systemctl status rock64-robot.service --no-pager

echo ""
echo "Step 2: Recent Service Logs (last 30 lines)"
echo "----------------------------------------------"
journalctl -u rock64-robot.service -n 30 --no-pager

echo ""
echo "Step 3: Check for Launch Process"
echo "----------------------------------------------"
pgrep -af "ros2 launch" || echo "No ros2 launch process found"

echo ""
echo "Step 4: Check ROS2 Environment in Service Context"
echo "----------------------------------------------"
# Show what environment the service is using
systemctl show rock64-robot.service --property=Environment

echo ""
echo "Step 5: Manual Launch Test"
echo "----------------------------------------------"
echo "Attempting manual launch to see if there are errors..."
cd /opt/rock64-robot/host_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
source /opt/rock64-robot/deployment/systemd/systemd_config.conf

echo "Environment check:"
echo "  ROS_DOMAIN_ID: $ROS_DOMAIN_ID"
echo "  SERIAL_PORT: $SERIAL_PORT"

echo ""
echo "Launching manually for 10 seconds to capture errors..."
timeout 10 ros2 launch robot_bringup rock64_bringup.launch.py \
  serial_port:="$SERIAL_PORT" \
  use_legacy_bridges:=true 2>&1 || echo "Launch failed or timed out"

echo ""
echo "=========================================="
echo "Log Analysis Complete"
echo "=========================================="
