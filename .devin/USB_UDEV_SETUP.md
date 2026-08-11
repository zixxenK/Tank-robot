# USB Device Plug-and-Play Setup

## Overview
This guide sets up persistent USB device identification for the Tank Robot, ensuring reliable device recognition regardless of port order or hub configuration.

## Prerequisites
- Rock64 with SSH access
- USB devices connected: STM32 CH340 adapter, PS5 controller (optional wired), ESP32-S3 (optional for flashing)

## Step 1: Get Device Serial Numbers

Run these commands to identify your devices and get their serial numbers:

```bash
# List all USB devices
lsusb

# Get detailed info for STM32 CH340 adapter (replace with your device bus/device)
lsusb -v -d 1a86:55d4 | grep iSerial

# Get detailed info for PS5 controller (if connected via USB)
lsusb -v -d 054c:0ce6 | grep iSerial

# Get detailed info for ESP32-S3 (if connected)
lsusb -v -d 303a:1001 | grep iSerial
```

**Expected output example:**
```
$ lsusb -v -d 1a86:55d4 | grep iSerial
  iSerial                  3 010123456789
```

## Step 2: Update Udev Rules File

Edit `.devin/99-tank-robot-usb.rules` and replace `SERIAL_NUMBER` placeholders with actual serials:

```bash
# Example after getting serials:
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="55d4", ATTRS{serial}=="010123456789", SYMLINK+="rock64_stm32", MODE="0666"
```

## Step 3: Install Udev Rules

```bash
# Copy rules to system directory
sudo cp .devin/99-tank-robot-usb.rules /etc/udev/rules.d/

# Reload udev rules
sudo udevadm control --reload-rules

# Trigger udev to apply rules immediately
sudo udevadm trigger

# Verify symlinks were created
ls -l /dev/rock64_stm32
ls -l /dev/ps5_controller  # if PS5 connected via USB
ls -l /dev/esp32_flash     # if ESP32 connected
```

## Step 4: Update Configuration Files

### Update STM32 Serial Port Configuration

Edit `host_ws/src/robot_bringup/config/rock64_hardware.yaml`:

```yaml
# Change from:
serial_port: /dev/rock64_stm32

# To (using persistent symlink):
serial_port: /dev/rock64_stm32
```

The path stays the same, but now it's a persistent symlink instead of a dynamic assignment.

### Update PS5 Controller Configuration

Edit `host_ws/src/robot_bringup/config/rock64_hardware.yaml`:

```yaml
# Change from:
joy_device: /dev/input/js0

# To (for wired USB connection):
joy_device: /dev/input/ps5_controller
```

**Note:** Bluetooth PS5 connections won't use the USB udev rule. For Bluetooth, you'll need to detect the device dynamically or use a different approach.

### Update ESP32 Flash Script

Update any ESP32 flash scripts to use `/dev/esp32_flash` instead of auto-detecting ports.

## Step 5: Rebuild and Test

```bash
cd ~/Tank-robot/host_ws
colcon build --symlink-install
source install/setup.bash

# Test with devices plugged in
ros2 launch robot_bringup rock64_bringup.launch.py
```

## Troubleshooting

### Devices Not Recognized After Plugging In

```bash
# Check udev logs
sudo journalctl -u systemd-udevd -f

# Test rule matching
sudo udevadm test --action=add /sys/bus/usb/devices/1-1

# Check if symlinks exist
ls -l /dev/rock64_stm32
```

### Multiple CH340 Devices Connected

If you have multiple CH340-family devices, the serial number matching becomes critical. The fallback rule without serial numbers may cause conflicts.

**Solution:** Ensure each device has a unique serial number in the udev rules.

### Permission Denied Errors

If you get permission errors accessing the serial port:

```bash
# Add your user to dialout group
sudo usermod -a -G dialout $USER

# Log out and back in for group change to take effect
```

### Serial Number Changes

Some cheap USB adapters don't have unique serial numbers or they change between reboots. If this happens:

1. Use the fallback rule without serial matching (less reliable)
2. Consider buying higher-quality adapters with proper serial numbers
3. Use USB port-specific rules (less portable between machines)

## Verification

After setup, verify plug-and-play works:

1. Unplug all USB devices
2. Plug them back in different USB ports
3. Check that symlinks still point to correct devices:
   ```bash
   ls -l /dev/rock64_stm32
   ls -l /dev/ps5_controller
   ```
4. Launch the robot and verify device connectivity

## Safety Notes

- **STM32 Bridge:** The serial port is safety-critical. Ensure the symlink always points to the correct device before enabling motors.
- **ESP32 Flashing:** Wrong device selection could flash the STM32 instead of ESP32. Always verify device identity before flashing.
- **PS5 Controller:** Incorrect device mapping could send wrong commands. Test in a safe area first.

## Alternative: Port-Specific Rules

If serial numbers aren't available, you can use USB port-specific rules:

```bash
# Find physical port path
ls -l /sys/class/tty/ttyUSB0
# Output: /sys/devices/platform/soc/20980000.usb/usb1/1-1/1-1:1.0/ttyUSB0

# Create rule based on physical port
KERNELS=="1-1:1.0", SUBSYSTEM=="tty", SYMLINK+="rock64_stm32", MODE="0666"
```

This is less portable between machines but more reliable if devices lack serial numbers.
