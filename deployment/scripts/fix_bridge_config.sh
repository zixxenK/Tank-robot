#!/usr/bin/env bash
# fix_bridge_config.sh - Configure ROS bridge to work with existing STM32 firmware
# Instead of rebuilding firmware, adapt the bridge to the existing setup

set -eo pipefail

echo "=========================================="
echo "Fix ROS Bridge Configuration"
echo "=========================================="

echo ""
echo "Step 1: Change bridge baud rate to match STM32 (9600)"
echo "----------------------------------------------"

CONFIG_FILE="/opt/rock64-robot/host_ws/install/robot_bringup/share/robot_bringup/config/rock64_hardware.yaml"
if [[ -f "$CONFIG_FILE" ]]; then
    echo "Current STM32 baud rate in config:"
    grep -A 2 "stm32_serial_bridge" "$CONFIG_FILE" || echo "Not found"
    
    echo ""
    echo "Changing baud rate from 115200 to 9600 to match existing STM32 firmware..."
    # Backup current config
    cp "$CONFIG_FILE" "${CONFIG_FILE}.backup"
    
    # Update baud rate
    sed -i 's/baud_rate: 115200/baud_rate: 9600/g' "$CONFIG_FILE"
    echo "✅ Updated baud rate to 9600"
else
    echo "❌ Configuration file not found: $CONFIG_FILE"
    exit 1
fi

echo ""
echo "Step 2: Update systemd config to use 9600 baud"
echo "----------------------------------------------"

SYSTEMD_CONFIG="/opt/rock64-robot/deployment/systemd/systemd_config.conf"
if [[ -f "$SYSTEMD_CONFIG" ]]; then
    if ! grep -q "STM32_BAUD" "$SYSTEMD_CONFIG"; then
        echo "Adding STM32_BAUD to systemd config..."
        echo "STM32_BAUD=9600" >> "$SYSTEMD_CONFIG"
        echo "✅ Added STM32_BAUD=9600"
    else
        sed -i "s|^STM32_BAUD=.*|STM32_BAUD=9600|" "$SYSTEMD_CONFIG"
        echo "✅ Updated STM32_BAUD to 9600"
    fi
fi

echo ""
echo "Step 3: Rebuild only the bridge package with new config"
echo "----------------------------------------------"

cd /opt/rock64-robot/host_ws
source /opt/ros/humble/setup.bash
colcon build --packages-select robot_drivers --symlink-install

echo ""
echo "Step 4: Restart service"
echo "----------------------------------------------"

systemctl restart rock64-robot.service

sleep 3
echo ""
echo "Service status:"
systemctl status rock64-robot.service --no-pager | head -15

echo ""
echo "Step 5: Check if bridge connects at 9600 baud"
echo "----------------------------------------------"

sleep 2
source install/setup.bash
echo "Running nodes:"
ros2 node list

echo ""
echo "STM32 bridge logs (last 10 lines):"
journalctl -u rock64-robot.service -n 10 --no-pager | grep -i "stm32\|baud\|bridge" || echo "No bridge logs found"

echo ""
echo "=========================================="
echo "Bridge Configuration Fix Complete"
echo "=========================================="

echo ""
echo "Summary:"
echo "--------"
echo "Baud rate changed to 9600 (matches existing STM32 firmware)"
echo "Service restarted with new configuration"
echo "Service Status: $(systemctl is-active rock64-robot.service)"

echo ""
echo "This approach:"
echo "- Uses your existing working STM32 firmware"
echo "- Only changes the ROS bridge baud rate"
echo "- Much simpler than rebuilding entire firmware"
echo "- Your PS5 controller should work as before"
