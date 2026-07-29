#!/usr/bin/env bash
# fix_ps5_device_path.sh - Configure PS5 bridge to use correct device path
# Run this to fix the PS5 controller device path issue

set -eo pipefail

echo "=========================================="
echo "Fix PS5 Controller Device Path"
echo "=========================================="

echo ""
echo "Step 1: Detect PS5 Controller Device"
echo "----------------------------------------------"

PS5_DEVICE=""
# Try event devices first (Bluetooth controllers)
for event in /dev/input/event*; do
    if [[ -e "$event" ]]; then
        if command -v evtest &>/dev/null; then
            DEVICE_INFO=$(timeout 1 evtest "$event" 2>&1 | head -3 || echo "")
            if echo "$DEVICE_INFO" | grep -qi "dualsense\|sony\|playstation"; then
                PS5_DEVICE="$event"
                echo "✅ Found PS5 controller at: $PS5_DEVICE"
                break
            fi
        fi
    fi
done

# Fallback to js0 if no event device found
if [[ -z "$PS5_DEVICE" && -e /dev/input/js0 ]]; then
    PS5_DEVICE="/dev/input/js0"
    echo "⚠️  Using fallback device: $PS5_DEVICE"
fi

if [[ -z "$PS5_DEVICE" ]]; then
    echo "❌ No PS5 controller device found"
    exit 1
fi

echo ""
echo "Step 2: Update PS5 Bridge Configuration"
echo "----------------------------------------------"

CONFIG_FILE="/opt/rock64-robot/host_ws/install/robot_bringup/share/robot_bringup/config/rock64_hardware.yaml"
if [[ -f "$CONFIG_FILE" ]]; then
    echo "Current PS5 device configuration:"
    grep -A 2 "ps5_ros_bridge" "$CONFIG_FILE" || echo "Not found in config"
    
    echo ""
    echo "Updating device path to $PS5_DEVICE..."
    # Backup current config
    cp "$CONFIG_FILE" "${CONFIG_FILE}.backup"
    
    # Update device path
    sed -i "s|device: /dev/input/js[0-9]|device: $PS5_DEVICE|g" "$CONFIG_FILE"
    echo "✅ Updated device path in configuration"
else
    echo "❌ Configuration file not found: $CONFIG_FILE"
    exit 1
fi

echo ""
echo "Step 3: Alternative - Update Bridge Parameters"
echo "----------------------------------------------"

# Some bridges use command-line parameters, so let's update systemd config
SYSTEMD_CONFIG="/opt/rock64-robot/deployment/systemd/systemd_config.conf"
if [[ -f "$SYSTEMD_CONFIG" ]]; then
    if ! grep -q "PS5_DEVICE" "$SYSTEMD_CONFIG"; then
        echo "Adding PS5_DEVICE to systemd config..."
        echo "PS5_DEVICE=$PS5_DEVICE" >> "$SYSTEMD_CONFIG"
        echo "✅ Added PS5_DEVICE to systemd config"
    else
        sed -i "s|^PS5_DEVICE=.*|PS5_DEVICE=$PS5_DEVICE|" "$SYSTEMD_CONFIG"
        echo "✅ Updated PS5_DEVICE in systemd config"
    fi
fi

echo ""
echo "Step 4: Update Launch Parameters"
echo "----------------------------------------------"

# Update robot_start.sh to pass PS5 device parameter
ROBOT_START="/opt/rock64-robot/deployment/scripts/robot_start.sh"
if [[ -f "$ROBOT_START" ]]; then
    echo "Checking robot_start.sh for PS5 device parameter..."
    if ! grep -q "ps5_device" "$ROBOT_START"; then
        echo "Adding PS5 device parameter to launch command..."
        # Add parameter to launch command
        sed -i 's|ros2 launch robot_bringup rock64_bringup.launch.py|ros2 launch robot_bringup rock64_bringup.launch.py ps5_device:="'"$PS5_DEVICE"'"|' "$ROBOT_START"
        echo "✅ Added ps5_device parameter to launch command"
    else
        sed -i "s|ps5_device:=.*|ps5_device:=$PS5_DEVICE|" "$ROBOT_START"
        echo "✅ Updated ps5_device parameter in launch command"
    fi
fi

echo ""
echo "Step 5: Restart Service"
echo "----------------------------------------------"

systemctl restart rock64-robot.service

sleep 3
echo ""
echo "Service status:"
systemctl status rock64-robot.service --no-pager | head -15

echo ""
echo "Step 6: Verify PS5 Bridge Status"
echo "----------------------------------------------"

sleep 2
source /opt/ros/humble/setup.bash
source /opt/rock64-robot/host_ws/install/setup.bash

echo "Running nodes:"
ros2 node list

echo ""
echo "PS5 bridge logs (last 10 lines):"
journalctl -u rock64-robot.service -n 10 --no-pager | grep -i "ps5" || echo "No PS5 logs found"

echo ""
echo "=========================================="
echo "PS5 Device Path Fix Complete"
echo "=========================================="

echo ""
echo "Summary:"
echo "--------"
echo "PS5 Device: $PS5_DEVICE"
echo "Config Updated: $CONFIG_FILE"
echo "Service Status: $(systemctl is-active rock64-robot.service)"

echo ""
echo "The PS5 bridge should now use the correct device path."
echo "Test by pressing buttons on the controller and checking:"
echo "  ros2 topic echo /joy"
