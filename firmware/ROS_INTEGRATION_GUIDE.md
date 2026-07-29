# STM32 Firmware ROS Integration - Quick Setup

## Changes Made

### 1. UART Baud Rate Fix
**File**: `firmware/stm32_chassis/Core/Src/usart.c`
**Change**: Line 108 - Changed USART2 baud rate from 9600 to 115200
```c
huart2.Init.BaudRate = 115200;  // Changed from 9600 for ROS2 compatibility
```

### 2. ROS Command Handler Integration
**New Files**:
- `firmware/stm32_chassis/Hiwonder/System/uart_ros_cmd.c` - ROS command parser
- `firmware/stm32_chassis/Hiwonder/System/uart_ros_cmd.h` - Header file
- `firmware/stm32_chassis/Hiwonder/System/uart_ros_integration.c` - UART callback integration
- `firmware/stm32_chassis/Hiwonder/System/uart_ros_integration.h` - Integration header

**Modified Files**:
- `firmware/stm32_chassis/Hiwonder/System/app.c` - Added includes and initialization

## Build and Flash Instructions

### On Your Development Machine (Windows)

```bash
cd C:\Projects\Tank-Robot\Tank-robot

# Build firmware
make stm32-build

# Flash firmware (requires ST-Link connected)
make stm32-flash
```

### On Rock64 (Alternative Build Location)

If you want to build on Rock64 (requires ARM toolchain):

```bash
cd /opt/rock64-robot
cd firmware/stm32_chassis
cmake -S . -B build -DCMAKE_TOOLCHAIN_FILE=cmake/stm32_toolchain.cmake
cmake --build build -j4
```

## Protocol Details

### ROS → STM32 Command Format
The ROS bridge sends commands in ASCII format:
```
<motor_id,direction,speed>\n
```

- `motor_id`: 0 = left motor, 1 = right motor
- `direction`: 0 = reverse, 1 = forward  
- `speed`: 0-255 (PWM duty cycle)

### STM32 → ROS Response Format
- Heartbeat: `HEARTBEAT\n`
- Acknowledgment: `ACK M<motor_id> D<direction> S<speed>\n`
- Stop acknowledgment: `ACK STOP\n`

### Special Commands
- `PING` - Request heartbeat
- `STOP` - Emergency stop all motors

## Testing After Flash

### 1. Test Serial Communication
```bash
# On Rock64
screen /dev/rock64_stm32 115200

# Send test command
<PING>
# Should receive: HEARTBEAT

# Send stop command
<STOP>
# Should receive: ACK STOP
```

### 2. Test Motor Commands
```bash
# Test left motor forward
<0,1,100>
# Should receive: ACK M0 D1 S100

# Test right motor forward  
<1,1,100>
# Should receive: ACK M1 D1 S100

# Stop both
<STOP>
```

### 3. Test with ROS2 Bridge
```bash
# On Rock64, after firmware is flashed
cd /opt/rock64-robot/host_ws
source install/setup.bash

# Launch ROS bridge
ros2 launch robot_bringup rock64_bringup.launch.py \
  serial_port:=/dev/rock64_stm32 \
  use_legacy_bridges:=true

# In another terminal, check bridge status
ros2 topic echo /stm32/bridge_alive
# Should show: data: true

# Send test command
ros2 topic pub --once /cmd_vel geometry_msgs/Twist "{linear: {x: 0.2}, angular: {z: 0.0}}"
```

## Troubleshooting

### Firmware Won't Build
```bash
# Clean build directory
cd firmware/stm32_chassis
rm -rf build
make stm32-build
```

### Flash Fails
```bash
# Check ST-Link connection
lsusb  # Should show ST-Link device

# Try manual flash with OpenOCD
openocd -f interface/stlink.cfg -f target/stm32f4x.cfg \
  -c "program firmware/stm32_chassis/build/tank_robot.elf verify reset exit"
```

### Motors Don't Respond
```bash
# Check serial communication
screen /dev/rock64_stm32 115200

# Verify baud rate
stty -F /dev/rock64_stm32

# Check ROS bridge logs
ros2 node info /stm32_serial_bridge
```

### Wrong Motor Direction
If motors move in reverse:
- Swap direction logic in `uart_ros_cmd.c`
- Or swap motor IDs in ROS bridge configuration

## Integration Points

The ROS integration is designed to work alongside existing Hiwonder code:

1. **Non-invasive**: Doesn't modify existing Hiwonder logic
2. **Layered**: ROS commands are translated to existing chassis API calls
3. **Compatible**: Works with existing PS5 controller via Bluetooth
4. **Safe**: Includes emergency stop and timeout protection

## Next Steps After Firmware Flash

1. Rebuild ROS2 workspace on Rock64:
```bash
cd /opt/rock64-robot
sudo bash deployment/scripts/quick_rebuild.sh
```

2. Test ROS2 launch:
```bash
cd /opt/rock64-robot/host_ws
source install/setup.bash
ros2 launch robot_bringup rock64_bringup.launch.py \
  serial_port:=/dev/rock64_stm32 \
  use_legacy_bridges:=true
```

3. Test with PS5 controller (already paired via Bluetooth):
```bash
# PS5 controller should work automatically via existing Bluetooth setup
# Just launch the bringup and the controller should connect
```

## Success Criteria

✅ Firmware builds without errors  
✅ Firmware flashes successfully  
✅ Serial communication at 115200 baud works  
✅ STM32 responds to PING command  
✅ Motors respond to ROS commands  
✅ PS5 controller controls robot via existing Bluetooth  
✅ System boots automatically with systemd service  
