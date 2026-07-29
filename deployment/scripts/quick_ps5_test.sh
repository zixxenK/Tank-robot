#!/usr/bin/env bash
# quick_ps5_test.sh - Quick PS5 controller test
# Run this on your PC to test PS5 controller connectivity

set -eo pipefail

echo "=========================================="
echo "PS5 Controller Quick Test"
echo "=========================================="

echo ""
echo "Step 1: Check controller connection..."
echo "----------------------------------------------"
if [[ -e /dev/input/js0 ]]; then
    echo "✅ Controller found at /dev/input/js0"
    ls -l /dev/input/js0
else
    echo "❌ Controller not found at /dev/input/js0"
    echo "Available input devices:"
    ls -la /dev/input/ 2>/dev/null || echo "No input devices found"
    echo ""
    echo "Connect your PS5 controller via USB-C and try again"
    exit 1
fi

echo ""
echo "Step 2: Install joystick tools (if needed)..."
echo "----------------------------------------------"
if ! command -v jstest &>/dev/null; then
    echo "Installing joystick tools..."
    sudo apt update && sudo apt install -y joystick
else
    echo "✅ joystick tools already installed"
fi

echo ""
echo "Step 3: Test controller with jstest..."
echo "----------------------------------------------"
echo "Press buttons and move sticks - should see values change"
echo "Press Ctrl+C to stop"
timeout 10 jstest /dev/input/js0 || echo "jstest completed or timed out"

echo ""
echo "Step 4: Check ROS2 installation..."
echo "----------------------------------------------"
if command -v ros2 &>/dev/null; then
    echo "✅ ROS2 found at: $(which ros2)"
    source /opt/ros/humble/setup.bash
else
    echo "❌ ROS2 not found - install ROS2 Humble first"
    echo "See deployment/docs/PC_TELEOP_SETUP.md for installation instructions"
    exit 1
fi

echo ""
echo "Step 5: Check robot workspace..."
echo "----------------------------------------------"
WS_PATH="${HOME}/Tank-robot/host_ws"
if [[ -d "${WS_PATH}" ]]; then
    echo "✅ Workspace found at ${WS_PATH}"
    if [[ -f "${WS_PATH}/install/setup.bash" ]]; then
        echo "✅ Workspace built"
        source "${WS_PATH}/install/setup.bash"
    else
        echo "❌ Workspace not built"
        echo "Build workspace:"
        echo "  cd ${WS_PATH}"
        echo "  colcon build --symlink-install"
        exit 1
    fi
else
    echo "❌ Workspace not found at ${WS_PATH}"
    echo "Clone repo:"
    echo "  cd ~"
    echo "  git clone https://github.com/zixxenK/Tank-robot.git"
    exit 1
fi

echo ""
echo "Step 6: Test joy node..."
echo "----------------------------------------------"
echo "Starting joy node for 5 seconds - move controller!"
timeout 5 ros2 run joy joy_node --ros-args -p dev:=/dev/input/js0 &
JOY_PID=$!

sleep 2

if ros2 topic list | grep -q "/joy"; then
    echo "✅ /joy topic found"
    echo "Sample data:"
    timeout 3 ros2 topic echo /joy --once || echo "No data received (move controller!)"
else
    echo "❌ /joy topic not found"
fi

kill $JOY_PID 2>/dev/null

echo ""
echo "Step 7: Check PS5 ROS bridge..."
echo "----------------------------------------------"
if ros2 pkg list | grep -q "robot_teleop"; then
    echo "✅ robot_teleop package found"
    echo "You can launch PS5 bridge with:"
    echo "  ros2 launch robot_teleop ps5_ros_bridge.launch.py"
else
    echo "❌ robot_teleop package not found"
    echo "Ensure workspace is built correctly"
fi

echo ""
echo "=========================================="
echo "PS5 Controller Test Complete"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. If controller test passed, setup multi-machine ROS2"
echo "2. Configure ROS_DOMAIN_ID=42 on both PC and Rock64"
echo "3. Start robot nodes on Rock64"
echo "4. Start PS5 bridge on PC"
echo ""
echo "See deployment/docs/PC_TELEOP_SETUP.md for full setup guide"
