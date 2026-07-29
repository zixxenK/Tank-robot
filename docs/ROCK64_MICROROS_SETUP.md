# Rock64 micro-ROS Setup Guide

This guide provides step-by-step instructions for setting up micro-ROS development on your Rock64 for the tank robot project.

## Prerequisites

### Hardware
- Rock64 board with Ubuntu 22.04 (or compatible ARM64 Linux)
- STM32F407 motor controller connected via UART
- Network connectivity for package installation

### Software
- ROS 2 Humble installed
- ARM cross-compilation toolchain
- CMake, colcon, and other build tools

## Step 1: Install Dependencies on Rock64

```bash
# Update package lists
sudo apt-get update

# Install ARM cross-compilation toolchain
sudo apt-get install gcc-arm-none-eabi libnewlib-arm-none-eabi libstdc++-arm-none-eabi-newlib

# Install build tools
sudo apt-get install cmake python3-colcon-common-extensions python3-rosdep

# Install micro-ROS agent
sudo apt-get install ros-humble-micro-ros-agent
```

## Step 2: Build micro-ROS Library for STM32

The micro-ROS library must be built on the Rock64 (or ARM64 Linux) for the STM32F407 Cortex-M4 processor.

```bash
# Navigate to your tank robot project directory
cd /path/to/Tank-robot

# Run the micro-ROS build script
bash scripts/build_microros.sh
```

### Build Script Details

The `build_microros.sh` script:
- Clones micro-ROS setup tools (if not present)
- Builds micro-ROS packages for STM32F407
- Generates static library: `firmware/stm32_chassis/micro_ros_lib/libmicroros.a`
- Generates headers: `firmware/stm32_chassis/micro_ros_lib/include/`

### Build Output

After successful build, you should see:
```
[build_microros] Build completed successfully
Output: firmware/stm32_chassis/micro_ros_lib/libmicroros.a
Headers: firmware/stm32_chassis/micro_ros_lib/include/
```

### Troubleshooting Build Issues

If the build fails:
1. Check ARM toolchain: `arm-none-eabi-gcc --version`
2. Verify ROS 2 sourcing: `source /opt/ros/humble/setup.bash`
3. Clear cache and retry: `rm -rf firmware/stm32_chassis/.cache/microros-build`
4. Check disk space: `df -h`

## Step 3: Build STM32 Firmware with micro-ROS

Once the micro-ROS library is built, compile the STM32 firmware:

```bash
cd firmware/stm32_chassis

# Configure build (Debug or Release)
cmake -B build -DCMAKE_BUILD_TYPE=Debug

# Build firmware
cmake --build build

# Output: build/factoryfirmwarestm32.bin and build/factoryfirmwarestm32.hex
```

### STM32 Firmware Features

The firmware now includes:
- **micro-ROS transport layer**: Custom UART implementation using USART6
- **micro-ROS node**: Subscribes to `/cmd_vel`, publishes motor telemetry
- **FreeRTOS integration**: micro-ROS runs in dedicated task
- **Conditional compilation**: Only builds if `libmicroros.a` is present

## Step 4: Build ROS2 Workspace

Build the ROS2 packages for the Rock64:

```bash
# Navigate to ROS2 workspace
cd ros2_ws

# Source ROS 2
source /opt/ros/humble/setup.bash

# Install dependencies
rosdep install --from-paths src --ignore-src -r -y

# Build workspace
colcon build --symlink-install

# Source the workspace
source install/setup.bash
```

### ROS2 Packages

- `robot_bringup`: Launch files and configuration
- `robot_drivers`: Hardware driver nodes (including legacy UART bridge)
- `robot_teleop`: Teleoperation interfaces (PS5, keyboard)
- `ros_robot_controller_msgs`: Custom message definitions
- `ros_robot_controller`: High-level robot controller

## Step 5: Launch the System

### Option 1: micro-ROS Mode (Recommended)

```bash
# Source ROS2 workspace
source /path/to/Tank-robot/ros2_ws/install/setup.bash

# Launch with micro-ROS agent enabled
ros2 launch robot_bringup rock64_bringup.launch.py \
    use_micro_ros:=true \
    use_legacy_bridges:=false \
    micro_ros_dev:=/dev/rock64_stm32 \
    micro_ros_baud:=115200
```

### Option 2: Legacy UART Bridge (Fallback)

```bash
# Source ROS2 workspace
source /path/to/Tank-robot/ros2_ws/install/setup.bash

# Launch with legacy Python UART bridge
ros2 launch robot_bringup rock64_bringup.launch.py \
    use_micro_ros:=false \
    use_legacy_bridges:=true \
    serial_port:=/dev/rock64_stm32
```

### Option 3: Parallel Operation (Migration Mode)

```bash
# Launch both micro-ROS and legacy bridges for testing
ros2 launch robot_bringup rock64_bringup.launch.py \
    use_micro_ros:=true \
    use_legacy_bridges:=true \
    use_binary_bridge:=false
```

## Step 6: Test Communication

### Test micro-ROS Communication

```bash
# In one terminal, launch the system
ros2 launch robot_bringup rock64_bringup.launch.py use_micro_ros:=true

# In another terminal, send velocity commands
ros2 topic pub /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.5}, angular: {z: 0.2}}"

# Monitor motor telemetry
ros2 topic echo /motor_left_speed
ros2 topic echo /motor_right_speed
```

### Verify micro-ROS Agent Status

```bash
# Check if micro-ROS agent is running
ros2 node list

# Should show micro-ROS agent and STM32 client nodes
```

## Architecture Overview

### Communication Flow

```
Rock64 (ROS2)              STM32F407 (micro-ROS)
┌─────────────────┐         ┌──────────────────────┐
│ micro-ROS Agent │◄────────►│ micro-ROS Client     │
│ (serial)        │ UART     │ (USART6 @ 115200)    │
└─────────────────┘         └──────────────────────┘
        │                           │
        ▼                           ▼
┌─────────────────┐         ┌──────────────────────┐
│ /cmd_vel pub    │         │ Motor Control         │
│ Motor telemetry │         │ PWM Generation        │
└─────────────────┘         └──────────────────────┘
```

### micro-ROS Topics

- **Subscribed by STM32**:
  - `/cmd_vel` (geometry_msgs/Twist): Velocity commands

- **Published by STM32**:
  - `/motor_left_speed` (std_msgs/Int32): Left motor speed
  - `/motor_right_speed` (std_msgs/Int32): Right motor speed

## Integration with Existing Motor Control

The micro-ROS node includes a placeholder function `apply_motor_commands()` that you need to integrate with your existing motor control code:

```c
// In microros_node.c, modify apply_motor_commands():
void apply_motor_commands(int16_t left_speed, int16_t right_speed) {
    // Integrate with your existing motor control
    // Example:
    // set_motor_pwm(MOTOR_LEFT, abs(left_speed), left_speed >= 0);
    // set_motor_pwm(MOTOR_RIGHT, abs(right_speed), right_speed >= 0);
}
```

## Performance Considerations

### Real-time Requirements
- **Motor control loops**: Keep local on STM32 (1kHz+)
- **micro-ROS processing**: Runs in FreeRTOS task (~10Hz spin)
- **UART communication**: 115200 baud (adjustable)

### Memory Usage
- **micro-ROS library**: ~100KB flash, ~30KB RAM
- **STM32F407 resources**: 192KB RAM (sufficient)
- **Stack sizes**: Adjust FreeRTOS task stacks if needed

## Troubleshooting

### micro-ROS Agent Connection Issues

```bash
# Check serial port permissions
ls -l /dev/rock64_stm32
sudo chmod 666 /dev/rock64_stm32

# Test serial communication
screen /dev/rock64_stm32 115200
```

### STM32 Firmware Issues

```bash
# Check if micro-ROS library was linked
arm-none-eabi-nm build/factoryfirmwarestm32.elf | grep rcl

# Verify UART configuration
# Check that USART6 is configured for 115200 baud
```

### ROS2 Communication Issues

```bash
# Check topic list
ros2 topic list

# Check node connectivity
ros2 node info /stm32_motor_controller

# Check topic statistics
ros2 topic info /cmd_vel --verbose
```

## Development Workflow

### Modify STM32 Code

1. Edit source files in `firmware/stm32_chassis/Core/Src/`
2. Rebuild firmware: `cd firmware/stm32_chassis && cmake --build build`
3. Flash to STM32 via ST-Link or J-Link
4. Test with ROS2 launch system

### Modify ROS2 Code

1. Edit Python/C++ nodes in `ros2_ws/src/`
2. Rebuild workspace: `cd ros2_ws && colcon build --symlink-install`
3. Source workspace: `source install/setup.bash`
4. Test with launch system

### Rebuild micro-ROS Library

Only needed if:
- Changing micro-ROS configuration
- Updating micro-ROS version
- Adding new message types

```bash
# Clear cache and rebuild
rm -rf firmware/stm32_chassis/.cache/microros-build
bash scripts/build_microros.sh
```

## Migration Path

### Phase 1: Current State
- Legacy UART bridge working
- micro-ROS infrastructure in place
- Both systems can run in parallel

### Phase 2: Testing
- Run micro-ROS alongside legacy bridge
- Verify motor control functionality
- Test telemetry publishing

### Phase 3: Transition
- Switch to micro-ROS primary
- Keep legacy as fallback
- Monitor performance and reliability

### Phase 4: Production
- Use micro-ROS exclusively
- Remove legacy bridge code
- Implement additional micro-ROS features

## Additional Resources

- [micro-ROS Documentation](https://micro.ros.org/docs/)
- [ROS 2 Humble Documentation](https://docs.ros.org/en/humble/)
- [STM32CubeMX Configuration](https://www.st.com/en/development-tools/stm32cubemx.html)

## Support

For issues specific to this project:
1. Check the main project README
2. Review the architecture documentation
3. Examine the build logs in `firmware/stm32_chassis/.cache/microros-build/`

For general micro-ROS issues:
- [micro-ROS GitHub Issues](https://github.com/micro-ROS/micro_ros_setup/issues)
- [ROS 2 Answers](https://answers.ros.org/)