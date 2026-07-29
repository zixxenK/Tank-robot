#!/usr/bin/env bash
# fix_controller_detection.sh - Fix PS5 controller detection and ROS2 configuration
# Run this on Rock64 to detect and configure PS5 controller properly

set -eo pipefail

echo "=========================================="
echo "PS5 Controller Detection & Configuration"
echo "=========================================="

echo ""
echo "Step 1: Check Available Input Devices"
echo "----------------------------------------------"

echo "All input devices:"
ls -la /dev/input/ 2>/dev/null || echo "No input devices found"

echo ""
echo "Joystick devices:"
ls -la /dev/input/js* 2>/dev/null || echo "No joystick devices found"

echo ""
echo "Event devices:"
ls -la /dev/input/event* 2>/dev/null | head -10 || echo "No event devices found"

echo ""
echo "Step 2: Check Bluetooth Devices"
echo "----------------------------------------------"

if command -v bluetoothctl &>/dev/null; then
    echo "Bluetooth devices:"
    bluetoothctl devices | grep -E "Device|Paired|Connected" || echo "No bluetooth devices found"
    
    echo ""
    echo "Bluetooth adapter status:"
    bluetoothctl show | grep -E "Powered|Discoverable" || echo "Cannot get adapter status"
else
    echo "Bluetooth control not available"
fi

echo ""
echo "Step 3: Check for USB Input Devices"
echo "----------------------------------------------"

echo "USB devices:"
lsusb | grep -i "sony\|playstation\|dualsense" || echo "No Sony/PlayStation devices found"

echo ""
echo "Step 4: Test Joystick Detection"
echo "----------------------------------------------"

if command -v jstest &>/dev/null; then
    echo "Joystick tool available - testing devices:"
    for js in /dev/input/js*; do
        if [[ -e "$js" ]]; then
            echo "Testing $js:"
            timeout 2 jstest "$js" 2>&1 | head -5 || echo "  No response"
        fi
    done
else
    echo "Installing joystick tools..."
    sudo apt install -y joystick
fi

echo ""
echo "Step 5: Create PS5 Controller Configuration"
echo "----------------------------------------------"

# Find potential PS5 controller devices
PS5_DEVICE=""
for device in /dev/input/js* /dev/input/event*; do
    if [[ -e "$device" ]]; then
        # Try to get device info
        if command -v evtest &>/dev/null; then
            DEVICE_INFO=$(timeout 1 evtest "$device" 2>&1 | head -3 || echo "")
            if echo "$DEVICE_INFO" | grep -qi "sony\|playstation\|dualsense"; then
                PS5_DEVICE="$device"
                break
            fi
        fi
    fi
done

if [[ -n "$PS5_DEVICE" ]]; then
    echo "✅ Found potential PS5 device: $PS5_DEVICE"
else
    echo "⚠️  No PS5 device detected via USB"
    echo "If using Bluetooth, the controller may appear as a different device type"
fi

echo ""
echo "Step 6: Fix ROS2 Environment Variables"
echo "----------------------------------------------"

CONFIG_FILE="/opt/rock64-robot/deployment/systemd/systemd_config.conf"
if [[ -f "$CONFIG_FILE" ]]; then
    echo "Current configuration:"
    cat "$CONFIG_FILE"
    
    echo ""
    echo "Adding missing ROS2 variables..."
    
    # Add ROS_DOMAIN_ID if missing
    if ! grep -q "ROS_DOMAIN_ID" "$CONFIG_FILE"; then
        echo "ROS_DOMAIN_ID=42" >> "$CONFIG_FILE"
        echo "✅ Added ROS_DOMAIN_ID=42"
    fi
    
    # Add RMW_IMPLEMENTATION if missing
    if ! grep -q "RMW_IMPLEMENTATION" "$CONFIG_FILE"; then
        echo "RMW_IMPLEMENTATION=rmw_fastrtps_cpp" >> "$CONFIG_FILE"
        echo "✅ Added RMW_IMPLEMENTATION=rmw_fastrtps_cpp"
    fi
    
    # Add ROS_LOCALHOST_ONLY if missing
    if ! grep -q "ROS_LOCALHOST_ONLY" "$CONFIG_FILE"; then
        echo "ROS_LOCALHOST_ONLY=0" >> "$CONFIG_FILE"
        echo "✅ Added ROS_LOCALHOST_ONLY=0"
    fi
else
    echo "Creating configuration file..."
    mkdir -p "$(dirname "$CONFIG_FILE")"
    cat > "$CONFIG_FILE" <<EOF
# Rock64 Ranger — Auto-generated Configuration
SERIAL_PORT=/dev/rock64_stm32
CAMERA_IP_STATION=192.168.1.125
ROS_DISTRO=humble
ROS_DOMAIN_ID=42
RMW_IMPLEMENTATION=rmw_fastrtps_cpp
ROBOT_NAMESPACE=rock64_1
ROS_LOCALHOST_ONLY=0
EOF
    echo "✅ Created configuration file"
fi

echo ""
echo "Step 7: Update systemd service environment"
echo "----------------------------------------------"

# Update the service to use the config file
SERVICE_FILE="/etc/systemd/system/rock64-robot.service"
if [[ -f "$SERVICE_FILE" ]]; then
    echo "Updating systemd service environment file path..."
    sed -i "s|^EnvironmentFile=.*|EnvironmentFile=$CONFIG_FILE|" "$SERVICE_FILE"
    systemctl daemon-reload
    echo "✅ Systemd service updated"
fi

echo ""
echo "Step 8: Restart service with new configuration"
echo "----------------------------------------------"

systemctl restart rock64-robot.service

sleep 3
echo ""
echo "Service status:"
systemctl status rock64-robot.service --no-pager | head -15

echo ""
echo "Step 9: Verify ROS2 environment after restart"
echo "----------------------------------------------"

sleep 2
source /opt/ros/humble/setup.bash
source /opt/rock64-robot/host_ws/install/setup.bash
source "$CONFIG_FILE"

echo "ROS2 Environment Variables:"
echo "  ROS_DOMAIN_ID: $ROS_DOMAIN_ID"
echo "  RMW_IMPLEMENTATION: $RMW_IMPLEMENTATION"
echo "  ROS_LOCALHOST_ONLY: $ROS_LOCALHOST_ONLY"

echo ""
echo "Step 10: Check nodes and topics"
echo "----------------------------------------------"

echo "Running nodes:"
ros2 node list

echo ""
echo "Available topics:"
ros2 topic list

echo ""
echo "=========================================="
echo "Controller Detection & Configuration Complete"
echo "=========================================="

echo ""
echo "Summary:"
echo "--------"
echo "PS5 Device: ${PS5_DEVICE:-Not found via USB}"
echo "ROS_DOMAIN_ID: $ROS_DOMAIN_ID"
echo "Service Status: $(systemctl is-active rock64-robot.service)"

echo ""
echo "PS5 Controller Options:"
echo "----------------------"
if [[ -n "$PS5_DEVICE" ]]; then
    echo "✅ USB controller detected - should work automatically"
else
    echo "⚠️  No USB controller found"
    echo ""
    echo "For Bluetooth PS5 controller:"
    echo "1. Ensure controller is paired: bluetoothctl"
    echo "2. Connect controller: bluetoothctl connect <controller_mac>"
    echo "3. Check if it appears as input device: ls -la /dev/input/"
    echo "4. If still not found, try USB connection instead"
fi

echo ""
echo "Next steps:"
echo "1. If PS5 controller is connected via Bluetooth, ensure it's paired"
echo "2. Try connecting via USB-C cable for simpler setup"
echo "3. For WSL Gazebo integration, run setup_wsl_gazebo.sh in WSL"
echo "4. Test communication: ros2 topic echo /cmd_vel"
