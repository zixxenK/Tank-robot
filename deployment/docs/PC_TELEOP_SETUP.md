# PS5 Controller Testing & PC Teleop Setup

## Overview
Test your PS5 controller and control the robot from your main PC while the ROS2 nodes run on the Rock64.

## Architecture
```
Your PC (Windows)              Rock64 (Ubuntu)
├── PS5 Controller      ◄────► ├── PS5 ROS Bridge
├── PS5 ROS Bridge      ◄────► ├── STM32 Serial Bridge  
├── RViz2 (optional)    ◄────► ├── Camera Bridge
└── ROS2 Domain 42             └── ROS2 Domain 42
```

## Step 1: Install ROS2 on Your PC

### Windows (WSL2 Recommended)
```bash
# Install Ubuntu 22.04 in WSL2
wsl --install -d Ubuntu-22.04

# In WSL2 Ubuntu, install ROS2 Humble
sudo apt update && sudo apt install software-properties-common
sudo add-apt-repository universe
sudo apt update && sudo apt install curl gnupg lsb-release
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null
sudo apt update
sudo apt install ros-humble-desktop python3-rosdep2
sudo rosdep init
rosdep update
```

### Linux (Ubuntu 22.04)
```bash
sudo apt update && sudo apt install software-properties-common
sudo add-apt-repository universe
sudo apt update && sudo apt install curl gnupg lsb-release
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null
sudo apt update
sudo apt install ros-humble-desktop python3-rosdep2
sudo rosdep init
rosdep update
```

## Step 2: Clone and Build Robot Workspace on PC

```bash
# Clone repo
cd ~
git clone https://github.com/zixxenK/Tank-robot.git
cd Tank-robot

# Build ROS2 workspace
cd host_ws
source /opt/ros/humble/setup.bash
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
```

## Step 3: Configure Multi-Machine ROS2 Communication

### On Both PC and Rock64:
```bash
# Set matching ROS2 domain ID
export ROS_DOMAIN_ID=42
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROBOT_NAMESPACE=rock64_1
```

### Configure Network Discovery
```bash
# Find your Rock64 IP (from your PC)
ping 192.168.1.139

# Set ROS_LOCALHOST_ONLY to false for network communication
export ROS_LOCALHOST_ONLY=0
```

## Step 4: Test PS5 Controller on PC

### Connect PS5 Controller
- **USB**: Connect via USB-C cable (simplest)
- **Bluetooth**: Pair with your PC/WSL2

### Test Controller Detection
```bash
# Install joystick tools
sudo apt install joystick

# Test controller
jstest /dev/input/js0
# Should show axis/button data when you move controller
```

### Verify in ROS2
```bash
cd ~/Tank-robot/host_ws
source install/setup.bash

# Check if joy node can see controller
ros2 run joy joy_node --ros-args -p dev:=/dev/input/js0

# In another terminal, check topics
ros2 topic list
ros2 topic echo /joy
# Should show controller data when you press buttons
```

## Step 5: Launch Teleop from PC

### Start Robot Nodes on Rock64
```bash
# SSH into Rock64
ssh root@192.168.1.139

# Start robot bringup
cd /opt/rock64-robot/host_ws
source install/setup.bash
export ROS_DOMAIN_ID=42
export ROS_LOCALHOST_ONLY=0

# Launch WITHOUT PS5 bridge (we'll run that on PC)
ros2 launch robot_bringup rock64_bringup.launch.py \
  serial_port:=/dev/rock64_stm32 \
  use_legacy_bridges:=true \
  camera_ip:=192.168.1.125
```

### Start PS5 Teleop Bridge on PC
```bash
cd ~/Tank-robot/host_ws
source install/setup.bash
export ROS_DOMAIN_ID=42
export ROS_LOCALHOST_ONLY=0

# Launch PS5 bridge only
ros2 launch robot_teleop ps5_ros_bridge.launch.py
```

### Alternative: Single-Command Launch from PC
```bash
# Modify launch to skip PS5 bridge on Rock64
# On Rock64:
ros2 launch robot_bringup rock64_bringup.launch.py \
  serial_port:=/dev/rock64_stm32 \
  use_legacy_bridges:=true \
  skip_ps5_bridge:=true

# On PC:
ros2 launch robot_teleop ps5_ros_bridge.launch.py
```

## Step 6: Verify Communication

### Check Topics (from either machine)
```bash
ros2 topic list
# Should see:
# /cmd_vel
# /joy
# /stm32/bridge_alive
# /camera/image_raw (if camera enabled)

# Test command flow
ros2 topic echo /cmd_vel
# Should show velocity commands when you move controller
```

### Check Nodes
```bash
ros2 node list
# Should see:
# /ps5_ros_bridge (on PC)
# /stm32_serial_bridge (on Rock64)
# /esp32_camera_bridge (on Rock64, if enabled)
```

## Step 7: Add RViz2 Visualization (Optional)

### Launch RViz2 on PC
```bash
cd ~/Tank-robot/host_ws
source install/setup.bash
export ROS_DOMAIN_ID=42
export ROS_LOCALHOST_ONLY=0

rviz2
```

### Configure RViz2
1. Add → RobotModel
2. Add → TF
3. Add → Image (for camera feed)
4. Set Fixed Frame to "base_link"

## Troubleshooting

### PS5 Controller Not Detected
```bash
# Check if controller is visible
ls /dev/input/js*

# If not found, try:
sudo apt install linux-modules-extra-raspi
# Or reconnect controller via USB
```

### ROS2 Nodes Not Communicating
```bash
# Check domain ID matches on both machines
echo $ROS_DOMAIN_ID

# Check network connectivity
ping 192.168.1.139

# Check ROS2 discovery
ROS_DOMAIN_ID=42 ros2 daemon start
ros2 topic list
```

### Firewall Issues
```bash
# On Rock64, allow ROS2 ports
sudo ufw allow 11311  # FastRTPS discovery
sudo ufw allow 7400-7402  # Additional RTPS ports
```

## Option 2: Gazebo Simulation on PC

If you want to test without real robot hardware:

### Launch Gazebo Simulation
```bash
cd ~/Tank-robot/host_ws
source install/setup.bash

ros2 launch robot_bringup gazebo_telemetry.launch.py
```

This launches:
- Gazebo world with robot model
- Teleop interface
- Visualization markers

### Test with PS5 Controller
```bash
# In another terminal
ros2 launch robot_teleop ps5_ros_bridge.launch.py
```

## Success Criteria

✅ PS5 controller detected and showing data in `/joy` topic  
✅ `/cmd_vel` commands generated when moving controller  
✅ Robot moves when controller is used (real or simulated)  
✅ RViz2 shows robot state (if enabled)  
✅ Low-latency response between controller and robot  

## Quick Test Script

```bash
#!/bin/bash
# quick_ps5_test.sh - Quick PS5 controller test

echo "Testing PS5 Controller..."

# Check controller
if [[ -e /dev/input/js0 ]]; then
    echo "✅ Controller found at /dev/input/js0"
else
    echo "❌ Controller not found"
    exit 1
fi

# Test joystick
timeout 5 jstest /dev/input/js0 || echo "jstest timed out (normal)"

# Source ROS2
source /opt/ros/humble/setup.bash
source ~/Tank-robot/host_ws/install/setup.bash

# Test joy node
echo "Starting joy node for 5 seconds..."
timeout 5 ros2 run joy joy_node --ros-args -p dev:=/dev/input/js0 &
JOY_PID=$!

# Check topics
sleep 2
if ros2 topic list | grep -q "/joy"; then
    echo "✅ /joy topic found"
    echo "Topic data:"
    timeout 3 ros2 topic echo /joy --once
else
    echo "❌ /joy topic not found"
fi

kill $JOY_PID 2>/dev/null
echo "Test complete"
```

## Next Steps

1. Get ROS2 running on your PC
2. Test PS5 controller detection
3. Configure multi-machine ROS2 communication
4. Start robot nodes on Rock64
5. Start PS5 teleop on PC
6. Test robot control
7. Add RViz2 visualization if desired
