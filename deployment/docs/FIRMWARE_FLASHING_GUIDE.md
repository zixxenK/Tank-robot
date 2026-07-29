# STM32 Firmware Flashing Guide

## Current Status

✅ **Serial Communication Working**: STM32 responds at 115200 baud  
❌ **Protocol Mismatch**: STM32 doesn't understand ROS commands yet  
❌ **Heartbeat Timeout**: STM32 not sending expected ROS protocol responses

## Solution: Flash Updated Firmware

The firmware has been updated with:
1. **Baud rate fix**: USART2 changed from 9600 to 115200 baud
2. **ROS command handler**: Added protocol translator for ROS commands
3. **UART integration**: Automatic command processing via interrupts

## Flashing Instructions (Windows PC)

### Prerequisites
- STM32F407 connected via ST-Link
- OpenOCD installed
- ARM toolchain installed
- Git repository cloned on Windows PC

### Step 1: Pull Latest Changes
```bash
cd C:\Projects\Tank-Robot\Tank-robot
git pull origin main
```

### Step 2: Build Firmware
```bash
make stm32-build
```

This will:
- Use STM32CubeMX configuration
- Compile with ARM toolchain
- Link with ROS command handler
- Generate firmware binary

### Step 3: Flash Firmware
```bash
make stm32-flash
```

This will:
- Connect via ST-Link
- Flash the updated firmware
- Verify flash integrity
- Reset the STM32

### Step 4: Verify Flashing
After flashing, the STM32 should:
- Boot normally
- Initialize USART2 at 115200 baud
- Respond to ROS commands in format: `<motor_id,direction,speed>\n`
- Send heartbeat responses: `HEARTBEAT\n`

## Testing After Flashing

### On Rock64:
```bash
# Test serial communication
screen /dev/rock64_stm32 115200

# Send test commands
<PING>
# Should receive: HEARTBEAT

<STOP>
# Should receive: ACK STOP

<0,1,100>
# Should receive: ACK M0 D1 S100
```

### Test ROS Bridge:
```bash
cd /opt/rock64-robot/host_ws
source install/setup.bash

# Restart service
sudo systemctl restart rock64-robot.service

# Check bridge status
ros2 topic echo /stm32/bridge_alive
# Should show: data: true

# Check diagnostics
ros2 topic echo /stm32/diagnostics
```

## Troubleshooting Flashing

### ST-Link Not Detected
```bash
# Check USB connection
lsusb | grep -i stlink

# reinstall drivers if needed
```

### Flash Fails
```bash
# Try manual flash with OpenOCD
cd firmware/stm32_chassis
openocd -f interface/stlink.cfg -f target/stm32f4x.cfg \
  -c "program build/tank_robot.elf verify reset exit"
```

### Wrong Baud Rate After Flash
- Verify usart.c has correct baud rate (115200)
- Rebuild and reflash
- Check clock configuration in STM32CubeMX

## Alternative: Test Without Flashing

To test the ROS2 stack without hardware:
```bash
# On Rock64, use simulation mode
ros2 launch robot_bringup gazebo_telemetry.launch.py
```

This will launch a simulated robot in Gazebo without needing the STM32.

## Firmware Changes Summary

### Files Modified:
- `firmware/stm32_chassis/Core/Src/usart.c` - Baud rate fix
- `firmware/stm32_chassis/Hiwonder/System/app.c` - ROS integration
- **New**: `firmware/stm32_chassis/Hiwonder/System/uart_ros_cmd.c` - ROS command parser
- **New**: `firmware/stm32_chassis/Hiwonder/System/uart_ros_cmd.h` - Header
- **New**: `firmware/stm32_chassis/Hiwonder/System/uart_ros_integration.c` - UART callbacks
- **New**: `firmware/stm32_chassis/Hiwonder/System/uart_ros_integration.h` - Integration header

### Protocol Details:
- **Input**: `<motor_id,direction,speed>\n` (ASCII)
- **Output**: `ACK M<motor_id> D<direction> S<speed>\n`
- **Heartbeat**: `HEARTBEAT\n` on PING
- **Emergency**: `ACK STOP\n` on STOP command

## Next Steps After Flashing

1. Flash firmware from Windows PC
2. Test serial communication from Rock64
3. Restart robot service
4. Verify PS5 controller works
5. Test motor control
6. Enable automatic boot verification

## Timeline

- **Flashing**: 5-10 minutes
- **Testing**: 10-15 minutes  
- **Total**: ~30 minutes to complete hardware integration

## Success Criteria

✅ STM32 responds to PING with HEARTBEAT  
✅ STM32 acknowledges motor commands  
✅ ROS bridge shows heartbeat alive  
✅ Motors respond to PS5 controller  
✅ System boots automatically with all nodes  
