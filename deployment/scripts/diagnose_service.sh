#!/usr/bin/env bash
# diagnose_service.sh - Check systemd service status and logs
# Run this to see what's happening with the rock64-robot service

set -eo pipefail  # Removed -u to allow undefined variables

echo "=========================================="
echo "Rock64 Robot Service Diagnostics"
echo "=========================================="

echo ""
echo "Step 1: Check service status..."
echo "----------------------------------------------"
sudo systemctl status rock64-robot.service --no-pager || true

echo ""
echo "Step 2: View recent service logs..."
echo "----------------------------------------------"
sudo journalctl -u rock64-robot.service -n 50 --no-pager

echo ""
echo "Step 3: Check if ROS2 is installed..."
echo "----------------------------------------------"
if command -v ros2 &>/dev/null; then
    echo "✅ ROS2 found at: $(which ros2)"
    echo "ROS_DISTRO: ${ROS_DISTRO:-not set}"
else
    echo "❌ ROS2 command not found"
    echo "Checking for ROS2 installation..."
    if [[ -d /opt/ros ]]; then
        echo "Found ROS installations in /opt/ros:"
        ls -la /opt/ros/
    else
        echo "No ROS2 installation found in /opt/ros"
    fi
fi

echo ""
echo "Step 4: Check workspace status..."
echo "----------------------------------------------"
WS_PATH="/opt/rock64-robot/host_ws"
if [[ -d "${WS_PATH}" ]]; then
    echo "Workspace exists: ${WS_PATH}"
    if [[ -f "${WS_PATH}/install/setup.bash" ]]; then
        echo "✅ Workspace built (install/setup.bash exists)"
    else
        echo "❌ Workspace not built (install/setup.bash missing)"
        echo "Current workspace contents:"
        ls -la "${WS_PATH}/"
    fi
else
    echo "❌ Workspace not found at ${WS_PATH}"
    echo "Checking for alternative workspace..."
    if [[ -d "/opt/rock64-robot/ros2_ws" ]]; then
        echo "Found ros2_ws instead"
        WS_PATH="/opt/rock64-robot/ros2_ws"
    fi
fi

echo ""
echo "Step 5: Test ROS2 environment sourcing..."
echo "----------------------------------------------"
if [[ -f "/opt/ros/humble/setup.bash" ]]; then
    echo "Found ROS2 Humble setup file"
    # Test sourcing
    if source /opt/ros/humble/setup.bash 2>/dev/null; then
        if command -v ros2 &>/dev/null; then
            echo "✅ ROS2 environment can be sourced successfully"
            echo "ROS2 version: $(ros2 --version 2>/dev/null || echo 'unknown')"
        else
            echo "❌ ROS2 still not available after sourcing"
        fi
    else
        echo "❌ Failed to source ROS2 environment"
    fi
else
    echo "❌ ROS2 Humble setup file not found"
fi

echo ""
echo "Step 6: Check device access..."
echo "----------------------------------------------"
if [[ -e /dev/rock64_stm32 ]]; then
    echo "✅ /dev/rock64_stm32 exists"
    ls -l /dev/rock64_stm32
else
    echo "❌ /dev/rock64_stm32 not found"
    echo "Available ACM devices:"
    ls -la /dev/ttyACM* 2>/dev/null || echo "None"
fi

echo ""
echo "=========================================="
echo "Diagnostics Complete"
echo "=========================================="
