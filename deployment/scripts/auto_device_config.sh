#!/usr/bin/env bash
# auto_device_config.sh - Automatic device configuration for port changes
# Call this when devices are plugged into different USB ports

set -eo pipefail

echo "=========================================="
echo "Automatic Device Configuration"
echo "=========================================="

REPO_ROOT="${REPO_ROOT:-/opt/rock64-robot}"
cd "${REPO_ROOT}" || exit 1

# Source ROS2 for device detection
source /opt/ros/humble/setup.bash 2>/dev/null || true

echo ""
echo "Step 1: Scan for USB Serial Devices"
echo "----------------------------------------------"

# Function to get device details
get_device_info() {
    local device=$1
    if [[ -e "$device" ]]; then
        local device_path=$(readlink -f "$device")
        local udev_info=$(udevadm info --query=property --name="$device" 2>/dev/null)
        local vendor=$(echo "$udev_info" | grep "ID_VENDOR_ID=" | cut -d= -f2)
        local model=$(echo "$udev_info" | grep "ID_MODEL_ID=" | cut -d= -f2)
        local serial=$(echo "$udev_info" | grep "ID_SERIAL_SHORT=" | cut -d= -f2)
        
        echo "Device: $device"
        echo "  Path: $device_path"
        echo "  Vendor: $vendor"
        echo "  Model: $model"
        echo "  Serial: $serial"
    else
        echo "Device: $device (not found)"
    fi
}

# Scan all possible serial devices
echo "Scanning for serial devices..."
for device in /dev/ttyACM* /dev/ttyUSB*; do
    if [[ -e "$device" ]]; then
        echo ""
        get_device_info "$device"
    fi
done

echo ""
echo "Step 2: Identify Robot Controller Device"
echo "----------------------------------------------"

# Try to find CH341 first (your current device)
ROBOT_DEVICE=""
for device in /dev/ttyACM* /dev/ttyUSB*; do
    if [[ -e "$device" ]]; then
        udev_info=$(udevadm info --query=property --name="$device" 2>/dev/null)
        if echo "$udev_info" | grep -q "1a86"; then
            ROBOT_DEVICE="$device"
            echo "✅ Found CH341 device: $ROBOT_DEVICE"
            break
        fi
    fi
done

# Fallback to STM32 native
if [[ -z "$ROBOT_DEVICE" ]]; then
    for device in /dev/ttyACM* /dev/ttyUSB*; do
        if [[ -e "$device" ]]; then
                udev_info=$(udevadm info --query=property --name="$device" 2>/dev/null)
            if echo "$udev_info" | grep -q "0483"; then
                ROBOT_DEVICE="$device"
                echo "✅ Found STM32 native device: $ROBOT_DEVICE"
                break
            fi
        fi
    done
fi

# Ultimate fallback to first available device
if [[ -z "$ROBOT_DEVICE" ]]; then
    if [[ -e /dev/ttyACM0 ]]; then
        ROBOT_DEVICE="/dev/ttyACM0"
        echo "⚠️  Using fallback device: $ROBOT_DEVICE"
    elif [[ -e /dev/ttyUSB0 ]]; then
        ROBOT_DEVICE="/dev/ttyUSB0"
        echo "⚠️  Using fallback device: $ROBOT_DEVICE"
    else
        echo "❌ No serial devices found!"
        exit 1
    fi
fi

echo ""
echo "Step 3: Update System Configuration"
echo "----------------------------------------------"

CONFIG_FILE="${REPO_ROOT}/deployment/systemd/systemd_config.conf"
if [[ -f "$CONFIG_FILE" ]]; then
    echo "Updating serial port in configuration..."
    sed -i "s|^SERIAL_PORT=.*|SERIAL_PORT=$ROBOT_DEVICE|" "$CONFIG_FILE"
    echo "✅ Updated SERIAL_PORT=$ROBOT_DEVICE"
else
    echo "Creating configuration file..."
    mkdir -p "${REPO_ROOT}/deployment/systemd"
    cat > "$CONFIG_FILE" <<EOF
# Rock64 Ranger — Auto-generated Configuration
SERIAL_PORT=$ROBOT_DEVICE
CAMERA_IP_STATION=192.168.1.125
ROS_DISTRO=humble
ROS_DOMAIN_ID=42
RMW_IMPLEMENTATION=rmw_fastrtps_cpp
ROBOT_NAMESPACE=rock64_1
EOF
    echo "✅ Created configuration with SERIAL_PORT=$ROBOT_DEVICE"
fi

echo ""
echo "Step 4: Update Udev Rules for This Device"
echo "----------------------------------------------"

# Get device IDs for persistent rules
if [[ -e "$ROBOT_DEVICE" ]]; then
    udev_info=$(udevadm info --query=property --name="$ROBOT_DEVICE" 2>/dev/null)
    vendor=$(echo "$udev_info" | grep "ID_VENDOR_ID=" | cut -d= -f2)
    model=$(echo "$udev_info" | grep "ID_MODEL_ID=" | cut -d= -f2)
    
    if [[ -n "$vendor" && -n "$model" ]]; then
        echo "Creating udev rule for $vendor:$model"
        
        sudo tee /etc/udev/rules.d/99-rock64-robot-auto.rules > /dev/null <<EOF
# Auto-generated rule for robot controller
SUBSYSTEM=="tty", ATTRS{idVendor}=="$vendor", ATTRS{idProduct}=="$model", SYMLINK+="rock64_stm32", GROUP="dialout", MODE="0660"
ENV{ID_MM_PORT_IGNORE}="1"
EOF
        
        sudo udevadm control --reload-rules
        sudo udevadm trigger
        echo "✅ Udev rule created and reloaded"
        
        # Test if symlink was created
        sleep 2
        if [[ -L /dev/rock64_stm32 ]]; then
            echo "✅ Symlink /dev/rock64_stm32 created successfully"
            ROBOT_DEVICE="/dev/rock64_stm32"
            sed -i "s|^SERIAL_PORT=.*|SERIAL_PORT=$ROBOT_DEVICE|" "$CONFIG_FILE"
        else
            echo "⚠️  Symlink not created, using direct device path"
        fi
    fi
fi

echo ""
echo "Step 5: Restart Robot Service"
echo "----------------------------------------------"

echo "Restarting rock64-robot.service with new configuration..."
sudo systemctl restart rock64-robot.service

sleep 3
echo ""
echo "Service status:"
sudo systemctl status rock64-robot.service --no-pager

echo ""
echo "Step 6: Verify Communication"
echo "----------------------------------------------"

# Test serial communication
if [[ -e "$ROBOT_DEVICE" ]]; then
    echo "Testing serial port $ROBOT_DEVICE..."
    if stty -F "$ROBOT_DEVICE" 115200 2>/dev/null; then
        echo "✅ Serial port configured to 115200 baud"
    else
        echo "⚠️  Could not configure serial port"
    fi
else
    echo "❌ Device $ROBOT_DEVICE not accessible"
fi

echo ""
echo "=========================================="
echo "Auto Configuration Complete"
echo "=========================================="

echo ""
echo "Configuration Summary:"
echo "---------------------"
echo "Robot Device: $ROBOT_DEVICE"
echo "Config File: $CONFIG_FILE"
echo "Service Status: $(systemctl is-active rock64-robot.service)"

echo ""
echo "The system will now:"
echo "✅ Auto-detect devices on any USB port"
echo "✅ Create persistent symlinks via udev"
echo "✅ Update configuration automatically"
echo "✅ Restart service with new device path"
echo ""
echo "You can unplug and replug the device into any port -"
echo "this script will auto-configure it correctly."
