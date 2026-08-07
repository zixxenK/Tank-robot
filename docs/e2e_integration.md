# End-to-End Integration Guide

## Package Build Status

All packages are properly configured with `ament_cmake_python` build system:

### ✅ Perception Package
- **CMakeLists.txt**: Installs `object_detector.py` and `obstacle_detector.py`
- **Launch**: `perception.launch.py` launches both perception nodes
- **Dependencies**: `rclpy`, `sensor_msgs`, `vision_msgs`, `geometry_msgs`, `cv_bridge`, `opencv-python`

### ✅ Navigation Package
- **CMakeLists.txt**: Installs `path_planner.py`
- **Launch**: `navigation.launch.py` launches path planner
- **Dependencies**: `rclpy`, `geometry_msgs`, `nav_msgs`, `numpy`

### ✅ Terrain Adaptation Package
- **CMakeLists.txt**: Installs `terrain_classifier.py` and `adaptive_controller.py`
- **Launch**: `terrain_adaptation.launch.py` launches both terrain nodes
- **Dependencies**: `rclpy`, `sensor_msgs`, `geometry_msgs`, `std_msgs`, `numpy`

### ✅ Robot Bringup Package
- **package.xml**: Updated with dependencies on perception, navigation, terrain_adaptation
- **Launch**: `full_stack.launch.py` launches complete autonomous stack

## Topic Wiring Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FULL AUTONOMOUS STACK                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────┐
│ ESP32 Camera     │
│ (esp32_camera   │
│  _bridge)       │
└────────┬─────────┘
         │ /camera/image_raw
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          PERCEPTION LAYER                                     │
├──────────────────┬──────────────────────────────────────────────────────────┤
│ Object Detector  │ Obstacle Detector                                       │
│ (HSV color seg)  │ (Edge + motion detection)                               │
└────────┬─────────┴──────────────────────────────────────────────────────────┘
         │ /perception/detections    │ /perception/obstacles
         │                           │ /perception/avoidance_vector
         ▼                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          NAVIGATION LAYER                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│ Path Planner (A*/Dijkstra/Simple)                                           │
│ Input: /goal_pose, /map                                                     │
│ Output: /cmd_vel_planned, /planned_path                                     │
└────────┬────────────────────────────────────────────────────────────────────┘
         │ /cmd_vel_planned
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      TERRAIN ADAPTATION LAYER                                │
├──────────────────┬──────────────────────────────────────────────────────────┤
│ Terrain          │ Adaptive Controller                                       │
│ Classifier       │ (IMU-based speed/power adjustment)                        │
│ (IMU → terrain)  │                                                          │
└────────┬─────────┴──────────────────────────────────────────────────────────┘
         │ /terrain/type
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          SAFETY LAYER                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│ Safety Gateway (agent_core)                                                 │
│ Input: /cmd_vel (from adaptive controller)                                  │
│ Output: /ranger/cmd_vel_safe (to STM32)                                     │
└────────┬────────────────────────────────────────────────────────────────────┘
         │ /ranger/cmd_vel_safe
         ▼
┌──────────────────┐
│ STM32 Hardware   │
│ (stm32_hardened  │
│  _bridge)        │
└──────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                          TELEMETY LAYER                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│ Telemetry Recorder (rosbag2)                                                │
│ Records: cmd_vel, encoder, imu, battery, odometry, camera, diagnostics     │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Topic Reference

### Input Topics (Hardware/External)
- `/camera/image_raw` - Camera images from ESP32
- `/stm32/imu` - IMU data from STM32
- `/stm32/encoder_ticks` - Motor encoder feedback
- `/stm32/joint_states` - Joint state telemetry
- `/stm32/battery` - Battery state
- `/stm32/odom` - Odometry
- `/stm32/diagnostics` - Hardware diagnostics
- `/map` - Occupancy grid for navigation
- `/goal_pose` - Navigation goal

### Output Topics (Perception)
- `/perception/detections` - Detected objects (Detection2DArray)
- `/perception/debug_image` - Debug visualization
- `/perception/obstacles` - Obstacle data (Float32MultiArray)
- `/perception/obstacle_debug` - Obstacle debug image
- `/perception/avoidance_vector` - Avoidance command (Twist)

### Output Topics (Navigation)
- `/planned_path` - Planned path (nav_msgs/Path)
- `/cmd_vel_planned` - Velocity command from planner

### Output Topics (Terrain Adaptation)
- `/terrain/type` - Terrain classification (String, format: "type:confidence")
- `/cmd_vel` - Adapted velocity command (to safety gateway)

### Safety Topics
- `/ranger/cmd_vel_safe` - Safety-gated command to STM32
- `/safety/e_stop` - Emergency stop signal
- `/stm32/bridge_alive` - Bridge heartbeat

## Launch Commands

### Individual Package Launch
```bash
# Perception only
ros2 launch perception perception.launch.py

# Navigation only
ros2 launch navigation navigation.launch.py

# Terrain adaptation only
ros2 launch terrain_adaptation terrain_adaptation.launch.py
```

### Full Autonomous Stack
```bash
# Launch all perception, navigation, and terrain adaptation nodes
ros2 launch robot_bringup full_stack.launch.py

# With optional components
ros2 launch robot_bringup full_stack.launch.py use_perception:=true use_navigation:=true use_terrain_adaptation:=true use_camera:=true
```

### Hardware Bringup (Existing)
```bash
# Launch safety gateway, teleop, STM32 bridge, camera bridge
ros2 launch robot_bringup rock64_bringup.launch.py
```

## Build Verification

To build all packages:
```bash
cd ~/Tank-robot/host_ws
colcon build --packages-select perception navigation terrain_adaptation robot_bringup
```

To source the workspace:
```bash
source install/setup.bash
```

## Data Flow Summary

1. **Camera → Perception**: ESP32 camera publishes images to `/camera/image_raw`
2. **Perception → Navigation**: Object/obstacle detections published for higher-level planning
3. **Navigation → Terrain**: Path planner outputs `/cmd_vel_planned`
4. **IMU → Terrain**: STM32 publishes IMU data to `/stm32/imu`
5. **Terrain → Safety**: Adaptive controller outputs adapted `/cmd_vel`
6. **Safety → Hardware**: Safety gateway outputs `/ranger/cmd_vel_safe` to STM32

## Configuration Files

All nodes use ROS2 parameters for configuration:
- Color ranges (HSV thresholds)
- Planner type (astar/dijkstra/simple)
- Terrain classification thresholds
- Control parameters per terrain type
- Camera IP and port

Parameters can be overridden via launch file arguments or YAML config files.
