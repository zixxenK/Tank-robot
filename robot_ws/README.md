# Rock64 Ranger ROS 2 Workspace Bootstrap

This folder contains a reproducible setup script that uses official ROS 2 package creation commands.

## Create And Populate The Workspace

Run on Rock64 after sourcing your ROS 2 environment:

```bash
cd ~/robot_ws
bash scripts/bootstrap_robot_ws.sh ~/robot_ws
```

If the folder does not exist yet:

```bash
mkdir -p ~/robot_ws
cd ~/robot_ws
# copy this repo's robot_ws folder contents here if needed
bash scripts/bootstrap_robot_ws.sh ~/robot_ws
```

## Commands Used By The Script

The script creates the workspace and packages with `ros2 pkg create`:

```bash
mkdir -p ~/robot_ws/src
cd ~/robot_ws/src
ros2 pkg create --build-type ament_python robot_drivers --dependencies rclpy geometry_msgs std_msgs sensor_msgs
ros2 pkg create --build-type ament_python robot_teleop --dependencies rclpy geometry_msgs sensor_msgs
ros2 pkg create --build-type ament_python robot_bringup --dependencies launch launch_ros rclpy
```

Then it creates nodes and updates entry points:

- robot_drivers:
  - stm32_bridge = robot_drivers.stm32_bridge:main
  - esp32_bridge = robot_drivers.esp32_bridge:main
- robot_teleop:
  - ps5_bridge = robot_teleop.ps5_bridge:main
- robot_bringup:
  - launch file: launch/robot_system.launch.py (starts all three nodes)

All setup.py files include:

- share/ament_index/resource_index/packages data_files marker
- package.xml installation
- package-specific launch/config installs where needed

## Build And Run

```bash
cd ~/robot_ws
colcon build --symlink-install
source install/setup.bash
ros2 launch robot_bringup robot_system.launch.py
```
