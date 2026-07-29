#!/usr/bin/env bash
# setup_wsl_gazebo.sh - Setup Gazebo integration from WSL Ubuntu to Rock64
# Run this in your WSL Ubuntu 22.04 to control the robot via Gazebo

set -eo pipefail

echo "=========================================="
echo "WSL Gazebo Integration Setup"
echo "=========================================="

echo ""
echo "Step 1: Check WSL Environment"
echo "----------------------------------------------"

# Check WSL version
echo "WSL Information:"
cat /etc/os-release | grep -E "NAME|VERSION"
uname -r

# Check network connectivity to Rock64
ROCK64_IP="192.168.1.139"
echo ""
echo "Testing connectivity to Rock64 ($ROCK64_IP)..."
if ping -c1 -W2 "$ROCK64_IP" &>/dev/null; then
    echo "✅ Rock64 reachable"
else
    echo "❌ Rock64 not reachable - check network connection"
    exit 1
fi

echo ""
echo "Step 2: Install ROS2 Humble (if not installed)"
echo "----------------------------------------------"

if ! command -v ros2 &>/dev/null; then
    echo "ROS2 not found - installing ROS2 Humble..."
    
    # Add ROS2 repository
    sudo apt update
    sudo apt install -y software-properties-common
    sudo add-apt-repository universe
    
    # Add ROS2 GPG key
    sudo apt install -y curl gnupg lsb-release
    sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null
    
    # Install ROS2 Humble
    sudo apt update
    sudo apt install -y ros-humble-desktop python3-rosdep2
    
    # Initialize rosdep (skip if already initialized)
    if [[ ! -f /etc/ros/rosdep/sources.list.d/20-default.list ]]; then
        sudo rosdep init
    else
        echo "rosdep already initialized, skipping init"
    fi
    rosdep update
    
    echo "✅ ROS2 Humble installed"
else
    echo "✅ ROS2 already installed: $(which ros2)"
fi

echo ""
echo "Step 3: Clone and Build Robot Workspace"
echo "----------------------------------------------"

WORKSPACE_DIR="$HOME/Tank-robot"
if [[ ! -d "$WORKSPACE_DIR" ]]; then
    echo "Cloning robot repository..."
    cd ~
    git clone https://github.com/zixxenK/Tank-robot.git
else
    echo "Repository already exists, pulling latest changes..."
    cd "$WORKSPACE_DIR"
    git pull origin main
fi

cd "$WORKSPACE_DIR/host_ws"

# Source ROS2
source /opt/ros/humble/setup.bash

# Install dependencies
echo "Installing dependencies..."
rosdep install --from-paths src --ignore-src -r -y

# Build workspace
echo "Building workspace..."
colcon build --symlink-install

echo "✅ Workspace built successfully"

echo ""
echo "Step 4: Configure Multi-Machine ROS2"
echo "----------------------------------------------"

# Set ROS2 domain ID to match Rock64
export ROS_DOMAIN_ID=42
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_LOCALHOST_ONLY=0

echo "ROS2 Configuration:"
echo "  ROS_DOMAIN_ID=$ROS_DOMAIN_ID"
echo "  RMW_IMPLEMENTATION=$RMW_IMPLEMENTATION"
echo "  ROS_LOCALHOST_ONLY=$ROS_LOCALHOST_ONLY"

# Add to .bashrc for persistence
if ! grep -q "ROS_DOMAIN_ID=42" ~/.bashrc; then
    echo ""
    echo "Adding ROS2 configuration to .bashrc..."
    cat >> ~/.bashrc <<'EOF'

# ROS2 Configuration for Tank Robot
export ROS_DOMAIN_ID=42
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_LOCALHOST_ONLY=0
EOF
    echo "✅ Configuration added to .bashrc"
fi

echo ""
echo "Step 5: Install Gazebo and Dependencies"
echo "----------------------------------------------"

sudo apt update
sudo apt install -y \
    gazebo11 \
    ros-humble-gazebo-ros-pkgs \
    ros-humble-ros2-control \
    ros-humble-ros2-controllers \
    ros-humble-xacro \
    ros-humble-robot-state-publisher \
    ros-humble-joint-state-publisher-gui

echo "✅ Gazebo and dependencies installed"

echo ""
echo "Step 6: Configure Network for ROS2 Discovery"
echo "----------------------------------------------"

# Allow ROS2 ports through firewall (if ufw is active)
if command -v ufw &>/dev/null; then
    echo "Configuring firewall..."
    sudo ufw allow 11311/udp  # FastRTPS discovery
    sudo ufw allow 7400:7410/udp  # Additional RTPS ports
    sudo ufw allow 7400:7410/tcp
    echo "✅ Firewall configured"
fi

echo ""
echo "Step 7: Test Multi-Machine Communication"
echo "----------------------------------------------"

# Source workspace
source install/setup.bash

echo "Testing ROS2 communication with Rock64..."
echo "Topics visible from Rock64:"
timeout 5 ros2 topic list 2>/dev/null || echo "No topics found (may need to start Rock64 nodes)"

echo ""
echo "Step 8: Launch Gazebo Simulation"
echo "----------------------------------------------"

echo "You can now launch Gazebo with:"
echo ""
echo "cd $WORKSPACE_DIR/host_ws"
echo "source install/setup.bash"
echo "export ROS_DOMAIN_ID=42"
echo "export ROS_LOCALHOST_ONLY=0"
echo ""
echo "# Option 1: Gazebo with telemetry"
echo "ros2 launch robot_bringup gazebo_telemetry.launch.py"
echo ""
echo "# Option 2: Connect to real robot on Rock64"
echo "# First ensure robot nodes are running on Rock64:"
echo "# ssh root@$ROCK64_IP 'cd /opt/rock64-robot/host_ws && source install/setup.bash && ros2 launch robot_bringup rock64_bringup.launch.py'"
echo ""
echo "# Then from WSL, you can:"
echo "ros2 topic echo /cmd_vel  # Monitor commands"
echo "ros2 topic echo /stm32/bridge_alive  # Check bridge status"
echo "rviz2  # Launch visualization"

echo ""
echo "=========================================="
echo "WSL Gazebo Setup Complete"
echo "=========================================="

echo ""
echo "Quick Start Commands:"
echo "--------------------"
echo "# Terminal 1 - Start Gazebo simulation"
echo "cd ~/Tank-robot/host_ws"
echo "source install/setup.bash"
echo "ros2 launch robot_bringup gazebo_telemetry.launch.py"
echo ""
echo "# Terminal 2 - Monitor robot state"
echo "cd ~/Tank-robot/host_ws"
echo "source install/setup.bash"
echo "ros2 topic list"
echo "ros2 topic echo /cmd_vel"
echo ""
echo "# For real robot control:"
echo "# 1. Start robot nodes on Rock64 (via SSH)"
echo "# 2. Use this WSL for monitoring and additional tools"
echo "# 3. PS5 controller connects via Bluetooth to Rock64 directly"
