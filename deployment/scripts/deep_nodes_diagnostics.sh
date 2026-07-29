#!/usr/bin/env bash
# deep_nodes_diagnostics.sh - Comprehensive ROS2 nodes and device diagnostics
# Handles device port changes and provides detailed node status

set -eo pipefail

echo "=========================================="
echo "ROS2 Nodes Deep Dive & Device Logic"
echo "=========================================="

REPO_ROOT="${REPO_ROOT:-/opt/rock64-robot}"
cd "${REPO_ROOT}" || exit 1

# Source ROS2
source /opt/ros/humble/setup.bash
source host_ws/install/setup.bash

echo ""
echo "Step 1: Expected vs Actual Node Analysis"
echo "----------------------------------------------"

# Expected nodes based on launch configuration
EXPECTED_NODES=(
    "ps5_ros_bridge"
    "stm32_serial_bridge"
    "esp32_camera_bridge"
)

echo "Expected nodes:"
for node in "${EXPECTED_NODES[@]}"; do
    echo "  - $node"
done

echo ""
echo "Actual running nodes:"
ACTUAL_NODES=$(ros2 node list 2>/dev/null || echo "")
if [[ -n "$ACTUAL_NODES" ]]; then
    echo "$ACTUAL_NODES" | while read -r node; do
        echo "  - $node"
    done
else
    echo "  No nodes found"
fi

echo ""
echo "Missing nodes:"
for node in "${EXPECTED_NODES[@]}"; do
    if ! echo "$ACTUAL_NODES" | grep -q "$node"; then
        echo "  ❌ $node (MISSING)"
    else
        echo "  ✅ $node (RUNNING)"
    fi
done

echo ""
echo "Step 2: Device Discovery & Port Mapping"
echo "----------------------------------------------"

# Check all ACM devices
echo "Available ACM devices:"
ls -la /dev/ttyACM* 2>/dev/null || echo "  No ACM devices found"

echo ""
echo "USB device details:"
lsusb | grep -i "1a86\|0483" || echo "  No STM32/CH341 devices found"

echo ""
echo "Current device symlinks:"
if [[ -L /dev/rock64_stm32 ]]; then
    echo "  /dev/rock64_stm32 -> $(readlink /dev/rock64_stm32)"
    echo "  Target exists: $([[ -e /dev/rock64_stm32 ]] && echo "YES" || echo "NO")"
else
    echo "  /dev/rock64_stm32 symlink not found"
fi

echo ""
echo "Step 3: Automatic Device Discovery Logic"
echo "----------------------------------------------"

# Function to find CH341 device
find_ch341_device() {
    local ch341_device=""
    for device in /dev/ttyACM* /dev/ttyUSB*; do
        if [[ -e "$device" ]]; then
            # Try to get device ID
            local device_path=$(readlink -f "$device")
            local device_id=$(udevadm info --query=property --name="$device" 2>/dev/null | grep -E "ID_VENDOR_ID|ID_MODEL_ID" || echo "")
            
            if echo "$device_id" | grep -q "1a86"; then
                ch341_device="$device"
                break
            fi
        fi
    done
    echo "$ch341_device"
}

# Function to find STM32 native device
find_stm32_device() {
    local stm32_device=""
    for device in /dev/ttyACM* /dev/ttyUSB*; do
        if [[ -e "$device" ]]; then
            local device_id=$(udevadm info --query=property --name="$device" 2>/dev/null | grep -E "ID_VENDOR_ID|ID_MODEL_ID" || echo "")
            
            if echo "$device_id" | grep -q "0483"; then
                stm32_device="$device"
                break
            fi
        fi
    done
    echo "$stm32_device"
}

CH341_DEVICE=$(find_ch341_device)
STM32_DEVICE=$(find_stm32_device)

echo "CH341 device discovery:"
if [[ -n "$CH341_DEVICE" ]]; then
    echo "  ✅ Found: $CH341_DEVICE"
else
    echo "  ❌ No CH341 device found"
fi

echo ""
echo "STM32 native device discovery:"
if [[ -n "$STM32_DEVICE" ]]; then
    echo "  ✅ Found: $STM32_DEVICE"
else
    echo "  ❌ No STM32 native device found"
fi

echo ""
echo "Step 4: Port Remapping Logic"
echo "----------------------------------------------"

# Auto-detect the correct serial port
AUTO_SERIAL_PORT=""
if [[ -n "$CH341_DEVICE" ]]; then
    AUTO_SERIAL_PORT="$CH341_DEVICE"
elif [[ -n "$STM32_DEVICE" ]]; then
    AUTO_SERIAL_PORT="$STM32_DEVICE"
elif [[ -e /dev/ttyACM0 ]]; then
    AUTO_SERIAL_PORT="/dev/ttyACM0"
elif [[ -e /dev/ttyUSB0 ]]; then
    AUTO_SERIAL_PORT="/dev/ttyUSB0"
fi

echo "Auto-detected serial port: ${AUTO_SERIAL_PORT:-NONE}"

# Update systemd config if needed
CONFIG_FILE="${REPO_ROOT}/deployment/systemd/systemd_config.conf"
if [[ -n "$AUTO_SERIAL_PORT" && "$AUTO_SERIAL_PORT" != "/dev/rock64_stm32" ]]; then
    echo ""
    echo "Step 5: Update System Configuration"
    echo "----------------------------------------------"
    echo "Current configured port: /dev/rock64_stm32"
    echo "Auto-detected port: $AUTO_SERIAL_PORT"
    
    if [[ -f "$CONFIG_FILE" ]]; then
        echo "Updating systemd_config.conf..."
        sed -i "s|^SERIAL_PORT=.*|SERIAL_PORT=$AUTO_SERIAL_PORT|" "$CONFIG_FILE"
        echo "✅ Configuration updated"
        
        echo ""
        echo "To apply changes, restart the service:"
        echo "  sudo systemctl restart rock64-robot.service"
    else
        echo "❌ Config file not found: $CONFIG_FILE"
    fi
fi

echo ""
echo "Step 6: Create/Update Udev Rules for Port Persistence"
echo "----------------------------------------------"

# Create robust udev rules
UDEV_RULES_FILE="/etc/udev/rules.d/99-rock64-robot.rules"

echo "Creating robust udev rules for device persistence..."
sudo tee "$UDEV_RULES_FILE" > /dev/null <<'EOF'
# Rock64 Robot - Robust Device Persistence Rules

# CH341 device (QinHeng Electronics) - creates rock64_stm32 symlink
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="55d4", SYMLINK+="rock64_stm32", MODE="0666"
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="55d4", ENV{ID_MM_PORT_IGNORE}="1"

# STM32 native USB-CDC - creates rock64_stm32_native symlink
SUBSYSTEM=="tty", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="5740", SYMLINK+="rock64_stm32_native", MODE="0666"

# Fallback rule for any ACM device if specific IDs don't match
KERNEL=="ttyACM[0-9]*", MODE="0666"
EOF

echo "✅ Udev rules updated"
sudo udevadm control --reload-rules
sudo udevadm trigger

echo ""
echo "Step 7: Service Health Check"
echo "----------------------------------------------"

SERVICE_STATUS=$(systemctl is-active rock64-robot.service)
echo "Service status: $SERVICE_STATUS"

if [[ "$SERVICE_STATUS" == "active" ]]; then
    echo "✅ Service is running"
    
    # Check service logs for errors
    echo ""
    echo "Recent service logs (last 20 lines):"
    journalctl -u rock64-robot.service -n 20 --no-pager | tail -20
else
    echo "❌ Service is not running"
    echo "Starting service..."
    sudo systemctl start rock64-robot.service
    sleep 3
    systemctl status rock64-robot.service --no-pager
fi

echo ""
echo "Step 8: Network Connectivity Check"
echo "----------------------------------------------"

# Check if camera is reachable
CAMERA_IP="${CAMERA_IP_STATION:-192.168.1.125}"
echo "Pinging camera at $CAMERA_IP..."
if ping -c1 -W2 "$CAMERA_IP" &>/dev/null; then
    echo "✅ Camera reachable"
else
    echo "❌ Camera not reachable"
fi

# Check network interface
echo ""
echo "Network interfaces:"
ip addr show | grep -E "inet |^[0-9]+:" | head -10

echo ""
echo "Step 9: ROS2 Domain and Communication Check"
echo "----------------------------------------------"

echo "ROS_DOMAIN_ID: ${ROS_DOMAIN_ID:-not set}"
echo "RMW_IMPLEMENTATION: ${RMW_IMPLEMENTATION:-not set}"
echo "ROS_LOCALHOST_ONLY: ${ROS_LOCALHOST_ONLY:-not set}"

echo ""
echo "ROS2 topics:"
ros2 topic list 2>/dev/null || echo "  No topics found"

echo ""
echo "ROS2 detailed node info:"
for node in $(ros2 node list 2>/dev/null); do
    echo "Node: $node"
    ros2 node info "$node" 2>/dev/null | head -5
    echo ""
done

echo ""
echo "=========================================="
echo "Diagnostics Complete"
echo "=========================================="

echo ""
echo "Summary:"
echo "--------"
echo "Nodes running: $(echo "$ACTUAL_NODES" | wc -l)"
echo "Serial port: ${AUTO_SERIAL_PORT:-NONE}"
echo "Service status: $SERVICE_STATUS"

echo ""
echo "Recommendations:"
echo "----------------"
if [[ -z "$AUTO_SERIAL_PORT" ]]; then
    echo "❌ No serial device found - connect STM32/CH341 device"
elif [[ "$SERVICE_STATUS" != "active" ]]; then
    echo "❌ Service not running - check logs with: journalctl -u rock64-robot.service -f"
elif [[ $(echo "$ACTUAL_NODES" | wc -l) -lt 2 ]]; then
    echo "⚠️  Few nodes running - expected at least 2 (ps5_ros_bridge, stm32_serial_bridge)"
else
    echo "✅ System appears operational"
fi

echo ""
echo "For device port changes, the system now:"
echo "1. Auto-detects CH341 and STM32 devices"
echo "2. Updates configuration automatically"
echo "3. Creates persistent symlinks via udev rules"
echo "4. Provides fallback to any available ACM device"
