# Tank Robot - Automatic Boot Remediation Plan

## Executive Summary
Critical issues preventing automatic boot have been identified across udev configuration, STM32 firmware, and protocol compatibility. This plan provides step-by-step fixes to achieve fully automated startup.

## Phase 1: Fix Device Access (Immediate)

### 1.1 Update Udev Rule
**File**: `host_ws/src/ros_robot_controller/scripts/99-ttyACM0.rules`

**Current Content**:
```
KERNEL=="ttyACM0", SUBSYSTEM=="tty", GROUP="ubuntu", MODE="0777"
ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="55d4", ENV{ID_MM_PORT_IGNORE}="1"
```

**Required Changes**:
```bash
# Create proper symlink for CH341 device
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="55d4", SYMLINK+="rock64_stm32", MODE="0666"
ENV{ID_MM_PORT_IGNORE}="1"
```

**Implementation**:
```bash
# On Rock64
sudo cp host_ws/src/ros_robot_controller/scripts/99-ttyACM0.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
# Verify symlink appears
ls -l /dev/rock64_stm32
```

### 1.2 Create Systemd Configuration
**File**: `deployment/systemd/systemd_config.conf`

**Create from example**:
```bash
cd /opt/rock64-robot
cp deployment/systemd/systemd_config.conf.example deployment/systemd/systemd_config.conf
```

**Edit values**:
```bash
# Network
ROCK64_IP=192.168.1.139  # Update to your actual IP

# Hardware
SERIAL_PORT=/dev/rock64_stm32
CAMERA_IP_STATION=192.168.1.125

# ROS2
ROS_DISTRO=humble
ROS_DOMAIN_ID=42
RMW_IMPLEMENTATION=rmw_fastrtps_cpp
ROBOT_NAMESPACE=rock64_1
```

## Phase 2: STM32 Firmware Fixes (Critical)

### 2.1 Fix UART Baud Rate
**File**: `firmware/stm32_chassis/Core/Src/usart.c`

**Change Line 108**:
```c
// Current: huart2.Init.BaudRate = 9600;
// Fixed:
huart2.Init.BaudRate = 115200;
```

**Rebuild Firmware**:
```bash
cd /opt/rock64-robot
make stm32-build
make stm32-flash  # Requires ST-Link
```

### 2.2 Add ROS Protocol Compatibility Layer
**File**: `firmware/stm32_chassis/Hiwonder/System/uart_ros_bridge.c` (NEW)

**Implementation**: Create a new UART handler that:
1. Listens for ASCII commands in format `<motor_id,direction,speed>\n`
2. Converts to Hiwonder chassis control calls
3. Sends heartbeat responses

**Pseudo-code**:
```c
void uart_ros_command_handler(char* cmd) {
    int motor_id, direction, speed;
    if (sscanf(cmd, "<%d,%d,%d>", &motor_id, &direction, &speed) == 3) {
        // Convert to chassis velocity
        float left_speed = (motor_id == 0) ? speed : 0;
        float right_speed = (motor_id == 1) ? speed : 0;
        
        if (direction == 0) { // Reverse
            left_speed = -left_speed;
            right_speed = -right_speed;
        }
        
        chassis->set_velocity(chassis, left_speed, right_speed, 0);
    }
}
```

### 2.3 Alternative: Use Binary Protocol
**Option**: Implement binary frame parser in STM32 firmware
**Complexity**: Higher but more robust
**Reference**: `host_ws/src/robot_drivers/robot_drivers/stm32_binary_bridge.py`

## Phase 3: ROS 2 Bridge Configuration

### 3.1 Ensure Correct Bridge Mode
**Default launch uses**: `use_legacy_bridges:=true`
**Bridge selected**: stm32_serial_bridge (ASCII format)

**Verify launch parameters**:
```bash
ros2 launch robot_bringup rock64_bringup.launch.py \
  use_legacy_bridges:=true \
  use_binary_bridge:=false \
  serial_port:=/dev/rock64_stm32 \
  camera_ip:=192.168.1.125 \
  use_camera_bridge:=false
```

### 3.2 Update Systemd Service
**File**: `deployment/systemd/rock64-robot.service`

**Ensure ExecStart uses correct parameters**:
```bash
ExecStart=/bin/bash /opt/rock64-robot/deployment/scripts/robot_start.sh
```

**The robot_start.sh should include**:
```bash
ros2 launch robot_bringup rock64_bringup.launch.py \
  host_workspace:="$(resolve_host_ws)" \
  serial_port:="${SERIAL_PORT}" \
  camera_ip:="${CAMERA_IP}" \
  use_camera_bridge:="${USE_CAMERA_BRIDGE}" \
  use_legacy_bridges:=true
```

## Phase 4: Verification Steps

### 4.1 Manual Testing Before Automation
```bash
# Test 1: Device access
ls -l /dev/rock64_stm32  # Should exist

# Test 2: Serial communication
screen /dev/rock64_stm32 115200  # Should see STM32 output

# Test 3: ROS 2 launch (manual)
cd /opt/rock64-robot/host_ws
source install/setup.bash
ros2 launch robot_bringup rock64_bringup.launch.py \
  serial_port:=/dev/rock64_stm32 \
  use_legacy_bridges:=true

# Test 4: Check topics
ros2 topic list
ros2 topic echo /cmd_vel
ros2 topic echo /stm32/bridge_alive
```

### 4.2 Systemd Service Testing
```bash
# Install service
sudo bash deployment/scripts/apply_systemd.sh

# Check status
sudo systemctl status rock64-robot.service

# View logs
journalctl -u rock64-robot.service -f

# Test restart
sudo systemctl restart rock64-robot.service
```

### 4.3 Boot Verification
```bash
# Reboot Rock64
sudo reboot

# After boot, check service
ssh root@192.168.1.139
sudo systemctl status rock64-robot.service

# Check ROS nodes
ros2 node list
ros2 topic list
```

## Phase 5: Long-term Improvements

### 5.1 Implement micro-ROS on STM32
**Benefits**: 
- Native ROS 2 integration
- No protocol translation layer
- Better reliability

**Steps**:
1. Build micro-ROS library: `make microros-build`
2. Implement micro-ROS client in STM32 firmware
3. Switch to `use_micro_ros:=true` mode

### 5.2 Add Health Monitoring
**Implementation**:
- Watchdog timer in STM32 firmware
- ROS 2 diagnostic aggregation
- Automatic recovery on failure

### 5.3 Data Visualization
**Options**:
- RViz2 configuration for robot state
- Web-based dashboard (Foxglove)
- Custom telemetry viewer

## Implementation Priority

**P0 (Critical for boot)**:
1. Fix udev rule (Phase 1.1)
2. Create systemd config (Phase 1.2)
3. Fix STM32 UART baud rate (Phase 2.1)
4. Add protocol compatibility layer (Phase 2.2)

**P1 (Important for reliability)**:
5. Manual verification (Phase 4.1)
6. Systemd service testing (Phase 4.2)
7. Boot verification (Phase 4.3)

**P2 (Enhancement)**:
8. micro-ROS implementation (Phase 5.1)
9. Health monitoring (Phase 5.2)
10. Data visualization (Phase 5.3)

## Troubleshooting

### Issue: /dev/rock64_stm32 not appearing
**Solution**: Check udev rule VID/PID match with `lsusb -v`

### Issue: STM32 not responding to commands
**Solution**: Verify baud rate match with `stty -F /dev/rock64_stm32`

### Issue: ROS bridge can't open serial port
**Solution**: Check permissions: `sudo chmod 666 /dev/rock64_stm32`

### Issue: Service fails to start
**Solution**: Check logs: `journalctl -u rock64-robot.service -n 50`

## Files to Modify

1. `host_ws/src/ros_robot_controller/scripts/99-ttyACM0.rules`
2. `deployment/systemd/systemd_config.conf` (create)
3. `firmware/stm32_chassis/Core/Src/usart.c`
4. `firmware/stm32_chassis/Hiwonder/System/uart_ros_bridge.c` (create)
5. `deployment/scripts/robot_start.sh` (verify parameters)

## Success Criteria

✅ Rock64 boots and systemd service starts automatically  
✅ /dev/rock64_stm32 symlink exists on boot  
✅ STM32 responds to ROS commands at 115200 baud  
✅ All ROS 2 nodes communicate: ps5_ros_bridge, stm32_serial_bridge  
✅ Motor control works via PS5 controller  
✅ System recovers from power cycle without intervention  
