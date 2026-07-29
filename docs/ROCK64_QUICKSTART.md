# Rock64 Quick Start Guide

## Current Status
✅ ROS2 workspace built successfully in `/opt/rock64-robot/host_ws`

## Install Dependencies (Alternative Methods)

### Option 1: Use Root Shell (If You Have Root Access)

```bash
# Switch to root shell
sudo -i

# Install ARM toolchain and dependencies
apt-get update
apt-get install gcc-arm-none-eabi libnewlib-arm-none-eabi libstdc++-arm-none-eabi-newlib
apt-get install cmake python3-colcon-common-extensions python3-rosdep
apt-get install ros-humble-micro-ros-agent

# Exit root shell
exit
```

### Option 2: Without Sudo (If You Don't Have Root Access)

If you don't have sudo access, you can install the ARM toolchain in your home directory:

```bash
# Download and install ARM toolchain locally
cd ~
wget https://developer.arm.com/-/media/Files/downloads/gnu-rm/10.3-2021.10/gcc-arm-none-eabi-10.3-2021.10-x86_64-linux.tar.bz2
tar -xjf gcc-arm-none-eabi-10.3-2021.10-x86_64-linux.tar.bz2

# Add to PATH
export PATH=$HOME/gcc-arm-none-eabi-10.3-2021.10/bin:$PATH

# Make permanent
echo 'export PATH=$HOME/gcc-arm-none-eabi-10.3-2021.10/bin:$PATH' >> ~/.bashrc
```

### Option 3: Check If Already Installed

The toolchain might already be installed. Check:

```bash
# Check if arm-none-eabi-gcc is available
which arm-none-eabi-gcc
arm-none-eabi-gcc --version
```

If it's already installed, you can skip the installation step.

## Build micro-ROS Library

Once you have the ARM toolchain available:

```bash
# Navigate to your project directory
cd /opt/rock64-robot

# If your tank-robot code is in a different location, adjust the path
# For example, if it's mounted from your Windows machine:
cd /mnt/c/Projects/Tank-Robot/Tank-robot

# Or if it's already on the Rock64:
cd /path/to/your/Tank-robot

# Run the micro-ROS build script
bash scripts/build_microros.sh
```

## Verify micro-ROS Agent Installation

Check if the micro-ROS agent is already installed (it might be in your ROS2 workspace):

```bash
# Check if micro-ros_agent is in the PATH
which micro-ros_agent

# Or check in the built workspace
ls /opt/rock64-robot/host_ws/install/micro_ros_agent/lib/micro_ros_agent/

# If found, you can use it directly
/opt/rock64-robot/host_ws/install/micro_ros_agent/lib/micro_ros_agent/micro_ros_agent --help
```

## Next Steps After micro-ROS Library Build

Once the micro-ROS library is built successfully:

```bash
# Build STM32 firmware
cd /path/to/Tank-robot/firmware/stm32_chassis
cmake -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build

# The output will be in build/factoryfirmwarestm32.bin and .hex
```

## Troubleshooting

### If You Can't Get Sudo Access

1. **Use the local ARM toolchain installation** (Option 2 above)
2. **Use the micro-ROS agent from your built workspace** (it's already built)
3. **Build the micro-ROS library** - this doesn't require sudo, just the ARM toolchain

### Check Current User Permissions

```bash
# Check what groups you're in
groups

# Check if you can use sudo without password (might be configured)
sudo -n whoami
```

### Alternative: Ask for Sudo Access

If you're working on a shared system, you might need to ask the administrator for:
- sudo access for package installation
- Or ask them to install the required packages:
  ```bash
  sudo apt-get install gcc-arm-none-eabi libnewlib-arm-none-eabi libstdc++-arm-none-eabi-newlib cmake python3-colcon-common-extensions python3-rosdep
  ```

## What You Can Do Right Now (Without Sudo)

Since your ROS2 workspace is already built and includes micro-ros_agent, you can:

1. **Test the current setup**:
   ```bash
   cd /opt/rock64-robot/host_ws
   source install/setup.bash
   micro-ros_agent --help
   ```

2. **Build micro-ROS library** (if you have ARM toolchain or install it locally)

3. **Test with legacy UART bridge** (doesn't require micro-ROS):
   ```bash
   source install/setup.bash
   ros2 launch robot_bringup rock64_bringup.launch.py use_micro_ros:=false use_legacy_bridges:=true
   ```

Let me know which approach works for your situation and I'll help you proceed!