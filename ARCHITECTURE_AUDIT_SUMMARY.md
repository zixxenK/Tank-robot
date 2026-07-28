# Tank Robot - Architecture Audit Summary

## Executive Summary

Your tank robot repository has a solid architectural foundation with ROS 2 Humble, STM32F407 motor control, and ESP32-S3 camera integration. However, **4 critical issues** are preventing automatic boot and proper communication between components.

## Critical Issues Identified

### 1. 🔴 Device Access Failure (udev rule mismatch)
- **Problem**: Udev rule targets wrong USB device ID
- **Expected**: `0483:5740` (STM32 native USB)  
- **Actual**: `1a86:55d4` (QinHeng CH341 USB-ACM)
- **Impact**: `/dev/rock64_stm32` symlink never created → ROS bridges can't connect
- **Fix**: Update udev rule with corrected VID/PID

### 2. 🔴 UART Baud Rate Mismatch
- **Problem**: STM32 USART2 configured for 9600 baud
- **Expected**: 115200 baud (per ROS bridge configuration)
- **Impact**: Complete communication failure
- **Fix**: Change `usart.c` line 108 from 9600 to 115200

### 3. 🔴 Protocol Incompatibility
- **Problem**: STM32 uses Hiwonder character protocol (A, B, C, I, S commands)
- **Expected**: ROS bridges send `<motor_id,direction,speed>\n` (ASCII) or binary frames
- **Impact**: Commands sent by ROS won't be understood by STM32
- **Fix**: Add protocol translation layer (provided)

### 4. 🔴 Missing Systemd Configuration
- **Problem**: `systemd_config.conf` doesn't exist (only example)
- **Impact**: Systemd service can't load environment variables
- **Fix**: Create configuration file from example

## Architecture Overview

### Hardware Components
```
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│   Rock64 SBC    │         │   STM32F407     │         │   ESP32-S3      │
│  (ROS 2 Host)   │         │  Motor Ctrl     │         │  Camera Node    │
│                 │         │                 │         │                 │
│  • Ubuntu 22.04 │         │  • FreeRTOS     │         │  • WiFi Station │
│  • ROS 2 Humble │         │  • USART2       │         │  • MJPEG Stream │
│  • PS5 Teleop   │◄────────►  • Motor PWM    │         │  • HTTP Port 81 │
└─────────────────┘  USB-UART└─────────────────┘         └─────────────────┘
       │                      │                              │
       │                      │                              │
       └──────────────────────┴──────────────────────────────┘
                      WiFi Network (192.168.1.x)
```

### Communication Protocols

#### Rock64 ↔ STM32 (UART)
- **Physical**: USB-UART via CH341 adapter (1a86:55d4)
- **Device**: `/dev/rock64_stm32` (udev symlink)
- **Baud**: 115200 (ROS side) / 9600 (STM32 side - **MISMATCH**)
- **ROS Protocol**: `<motor_id,direction,speed>\n` (ASCII)
- **STM32 Protocol**: Hiwonder character commands (A, B, C, I, S)
- **Bridge**: `stm32_serial_bridge.py` (ASCII) or `stm32_binary_bridge.py` (binary)

#### Rock64 ↔ ESP32 (HTTP)
- **Physical**: WiFi (station mode)
- **Protocol**: HTTP MJPEG stream
- **URL**: `http://192.168.1.125:81/stream`
- **Bridge**: `esp32_camera_bridge.py`
- **ROS Topic**: `/camera/image_raw`

### ROS 2 Node Architecture
```
rock64_bringup.launch.py
├── ps5_ros_bridge (node)
│   └── Subscribes: /joy (PS5 controller)
│   └── Publishes: /cmd_vel (velocity commands)
├── stm32_serial_bridge (node)
│   └── Subscribes: /cmd_vel
│   └── Publishes: /stm32/bridge_alive, /stm32/diagnostics
│   └── Serial: /dev/rock64_stm32 @ 115200 baud
└── esp32_camera_bridge (node)
    └── Publishes: /camera/image_raw
    └── HTTP: http://192.168.1.125:81/stream
```

### Boot Sequence
```
Power On
    ↓
systemd: rock64-robot.service
    ↓
robot_start.sh
    ↓
source_ros2_ws.sh (ROS 2 environment setup)
    ↓
rock64_bringup.launch.py
    ↓
[ps5_ros_bridge] + [stm32_serial_bridge] + [esp32_camera_bridge]
    ↓
Fully Operational Robot
```

## Current Bottlenecks

### Before Fixes
1. ❌ Device symlink missing → bridges can't open serial port
2. ❌ Baud rate mismatch → garbage data on UART
3. ❌ Protocol mismatch → STM32 doesn't understand ROS commands
4. ❌ Systemd config missing → service can't load parameters

### After Fixes
1. ✅ Device symlink created → serial port accessible
2. ✅ Baud rate matched → clean UART communication
3. ✅ Protocol translation → commands understood
4. ✅ Systemd configured → automatic boot enabled

## Remediation Files Provided

### 1. Quick Fix Script
**File**: `deployment/scripts/quick_fix_device_access.sh`
**Purpose**: Automates device access and systemd configuration fixes
**Usage**: `sudo bash deployment/scripts/quick_fix_device_access.sh`

### 2. Complete Remediation Plan
**File**: `deployment/REMEDIATION_PLAN.md`
**Purpose**: Detailed step-by-step fix implementation guide
**Contents**: All fixes with verification steps and troubleshooting

### 3. Protocol Bridge Implementation
**Files**: 
- `firmware/stm32_chassis/Hiwonder/System/uart_ros_bridge.c`
- `firmware/stm32_chassis/Hiwonder/System/uart_ros_bridge.h`

**Purpose**: Translate ROS ASCII commands to Hiwonder chassis control
**Integration**: Add to STM32 firmware build and call from UART interrupt handler

## Implementation Priority

### Phase 1: Device Access (30 minutes)
```bash
# Run on Rock64
sudo bash deployment/scripts/quick_fix_device_access.sh

# Verify device appears
ls -l /dev/rock64_stm32
```

### Phase 2: STM32 Firmware Fixes (1-2 hours)
```bash
# Fix baud rate in firmware/stm32_chassis/Core/Src/usart.c
# Line 108: Change from 9600 to 115200

# Add protocol bridge to firmware
# Integrate uart_ros_bridge.c/.h into build

# Rebuild and flash
cd /opt/rock64-robot
make stm32-build
make stm32-flash
```

### Phase 3: Manual Testing (30 minutes)
```bash
# Test ROS launch manually
cd /opt/rock64-robot/host_ws
source install/setup.bash
ros2 launch robot_bringup rock64_bringup.launch.py \
  serial_port:=/dev/rock64_stm32 \
  use_legacy_bridges:=true

# Verify topics
ros2 topic list
ros2 topic echo /cmd_vel
ros2 topic echo /stm32/bridge_alive
```

### Phase 4: Systemd Automation (15 minutes)
```bash
# Install and enable service
sudo bash deployment/scripts/apply_systemd.sh

# Test service
sudo systemctl status rock64-robot.service
sudo systemctl restart rock64-robot.service

# Reboot test
sudo reboot
# After boot, verify service is running
```

## Verification Checklist

- [ ] `/dev/rock64_stm32` symlink exists after connecting USB
- [ ] STM32 firmware rebuilt with 115200 baud
- [ ] Protocol bridge integrated into firmware
- [ ] Manual ROS launch shows all nodes running
- [ ] `/stm32/bridge_alive` topic publishes `true`
- [ ] Motor control responds to PS5 controller input
- [ ] Systemd service starts automatically on boot
- [ ] Service recovers from power cycle without intervention

## Success Criteria

✅ **Automatic Boot**: Rock64 powers on and all ROS 2 nodes start automatically  
✅ **Device Access**: Serial port accessible via consistent symlink  
✅ **Communication**: Clean UART communication at correct baud rate  
✅ **Protocol Translation**: ROS commands understood by STM32  
✅ **Motor Control**: Robot responds to PS5 controller input  
✅ **Reliability**: System recovers from power cycle without manual intervention  

## Troubleshooting

### Device Not Appearing
```bash
# Check USB device
lsusb -v | grep -i 1a86

# Check udev rules
sudo udevadm info --attribute-walk --name=/dev/ttyACM0

# Manually trigger udev
sudo udevadm trigger
sudo udevadm control --reload-rules
```

### Communication Failure
```bash
# Test serial connection
screen /dev/rock64_stm32 115200

# Check baud rate
stty -F /dev/rock64_stm32

# Monitor UART traffic
sudo picocom /dev/rock64_stm32 -b 115200
```

### ROS Bridge Issues
```bash
# Check bridge node status
ros2 node list
ros2 node info /stm32_serial_bridge

# Check diagnostic topics
ros2 topic echo /stm32/diagnostics
ros2 topic echo /stm32/bridge_alive
```

### Systemd Service Issues
```bash
# Check service status
sudo systemctl status rock64-robot.service

# View logs
journalctl -u rock64-robot.service -f

# Check service configuration
systemctl cat rock64-robot.service
```

## Next Steps

1. **Immediate**: Run `quick_fix_device_access.sh` on Rock64
2. **Short-term**: Apply STM32 firmware fixes and rebuild
3. **Medium-term**: Test manual ROS launch and verify communication
4. **Long-term**: Enable systemd service and verify automatic boot

## Support Files

- **Communication Protocols**: `docs/communication_protocols.md`
- **Deployment Guide**: `deployment/docs/deployment_guide.md`
- **Remediation Plan**: `deployment/REMEDIATION_PLAN.md`
- **Quick Fix Script**: `deployment/scripts/quick_fix_device_access.sh`
- **Protocol Bridge**: `firmware/stm32_chassis/Hiwonder/System/uart_ros_bridge.c`

## Conclusion

The architecture is sound with proper separation of concerns and modern ROS 2 integration. The blocking issues are all configuration/firmware problems that can be resolved with the provided fixes. Once these 4 critical issues are addressed, your tank robot will achieve fully automatic boot with all ROS 2 nodes communicating properly.
