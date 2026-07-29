# Robotics Engineering Checklist - Rock64 Ranger Tank Robot

## Overview
This comprehensive checklist covers all systems and dependencies required to get the tank robot fully operational. Use this checklist to verify completion of each engineering domain before attempting autonomous or teleop driving.

---

## END-TO-END OPERATIONAL PROCEDURES

This section provides complete step-by-step commands for all operations, including terminal locations, folder navigation, and command explanations.

### DEVELOPMENT MACHINE SETUP (Windows/WSL)

#### Terminal: Windows PowerShell (Administrator)
**Location:** Your development machine

```powershell
# Navigate to project directory
cd C:\Projects\Tank-Robot\Tank-robot

# Run Windows development environment bootstrap
# This installs ARM toolchain, sets up PATH, and configures build environment
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap_windows_dev.ps1 -PersistUserPath
```

**What this does:**
- Navigates to the tank robot project directory
- Runs the bootstrap script to install development tools
- Sets up environment variables for ARM GCC and CMake
- Persists PATH changes to your user profile for future sessions

#### Terminal: WSL Ubuntu (if using WSL for ROS2 builds)
**Location:** Your development machine

```powershell
# Navigate to project directory in WSL
cd /mnt/c/Projects/Tank-Robot/Tank-robot

# Build ROS2 workspace in WSL
powershell -ExecutionPolicy Bypass -File .\scripts\build_host_wsl.ps1 -Distro Ubuntu-22.04 -RosDistro humble
```

**What this does:**
- Accesses the Windows project directory from WSL
- Builds the ROS2 host workspace using WSL Ubuntu
- Sources ROS2 Humble environment automatically
- Runs colcon build with symlink-install for faster development

---

### ROCK64 INITIAL SETUP

#### Terminal: SSH to Rock64
**Location:** Remote connection to Rock64 SBC (192.168.1.139)

```bash
# SSH into the Rock64
ssh rock64@192.168.1.139

# Navigate to project directory (if already cloned)
cd /opt/rock64-robot

# OR clone the repository if this is first-time setup
sudo git clone https://github.com/zixxenK/Tank-robot /opt/rock64-robot
cd /opt/rock64-robot
```

**What this does:**
- Connects to the Rock64 SBC via SSH
- Navigates to the robot project directory
- Clones the repository if this is a fresh setup
- Uses /opt/ for system-wide installation

#### Terminal: SSH to Rock64 (continued)
**Location:** Rock64 SBC

```bash
# Run the Rock64 setup script
# This installs ROS2, dependencies, builds workspace, and configures systemd
sudo bash deployment/scripts/rock64_setup.sh --ros-distro auto

# The script will:
# 1. Detect Ubuntu version and install appropriate ROS2 distro
# 2. Install system dependencies (Python3, colcon, build tools)
# 3. Build the ROS2 workspace
# 4. Configure udev rules for serial devices
# 5. Install and enable systemd service for auto-start
```

**What this does:**
- Runs the comprehensive Rock64 setup script
- Automatically detects OS version and installs ROS2 (Humble for 22.04, Jazzy for 24.04)
- Installs all required Python dependencies
- Builds the ROS2 workspace with colcon
- Sets up hardware permissions (serial ports, GPIO, I2C)
- Configures the robot to start automatically on boot

---

### STM32 FIRMWARE BUILD & FLASH

#### Terminal: Windows PowerShell
**Location:** Development machine

```powershell
# Navigate to project root
cd C:\Projects\Tank-Robot\Tank-robot

# Build and flash STM32 firmware with verification
powershell -ExecutionPolicy Bypass -File .\scripts\flash_stm32_windows.ps1 -Build -Verify

# For full chip erase before flashing (use if experiencing issues)
powershell -ExecutionPolicy Bypass -File .\scripts\flash_stm32_windows.ps1 -Build -Erase -Verify
```

**What this does:**
- Navigates to project directory
- Runs the STM32 build and flash script
- Builds the STM32 firmware using CMake and ARM GCC toolchain
- Flashes the firmware via ST-Link V2/V3 using OpenOCD
- Verifies the flash contents to ensure successful programming
- Optionally performs full chip erase to clear any existing firmware

#### Terminal: Windows PowerShell (Manual Build)
**Location:** Development machine

```powershell
# Navigate to STM32 firmware directory
cd C:\Projects\Tank-Robot\Tank-robot\firmware\stm32_chassis

# Configure CMake build with ARM toolchain
cmake -S . -B build -DCMAKE_TOOLCHAIN_FILE=cmake/stm32_toolchain.cmake

# Build the firmware
cmake --build build -j4

# The output binary will be at: build/factoryfirmwarestm32.bin
```

**What this does:**
- Changes to the STM32 firmware directory
- Configures CMake to use the ARM cross-compilation toolchain
- Builds the firmware with 4 parallel jobs for speed
- Generates the binary file ready for flashing

#### Terminal: Linux/WSL (Alternative)
**Location:** Development machine or WSL

```bash
# Navigate to project directory
cd /mnt/c/Projects/Tank-Robot/Tank-robot

# Build and flash STM32 firmware
bash scripts/flash_stm32.sh --build --verify

# Flash with full chip erase
bash scripts/flash_stm32.sh --build --erase --verify
```

**What this does:**
- Same functionality as Windows version but uses bash instead of PowerShell
- Uses OpenOCD for programming the STM32 via ST-Link
- Verifies flash contents after programming

---

### ESP32 FIRMWARE BUILD & FLASH

#### Terminal: Windows PowerShell or Linux Terminal
**Location:** Development machine

```powershell
# Navigate to ESP32 firmware directory
cd C:\Projects\Tank-Robot\Tank-robot\firmware\esp32_sensors

# Build the firmware
pio run -e esp32cam

# Flash the firmware to connected ESP32
pio run -e esp32cam -t upload

# Monitor serial output (for debugging)
pio device monitor -p /dev/ttyUSB0 -b 115200
```

**What this does:**
- Changes to the ESP32 firmware directory
- Uses PlatformIO to build the ESP32 firmware
- Uploads the firmware to the ESP32-S3 via USB
- Opens a serial monitor to view debug output from the ESP32

#### Terminal: Windows PowerShell (WiFi Configuration)
**Location:** Development machine

```powershell
# Navigate to ESP32 include directory
cd C:\Projects\Tank-Robot\Tank-robot\firmware\esp32_sensors\include

# Create or edit secrets.h file with WiFi credentials
notepad secrets.h
```

**Add the following content to secrets.h:**
```cpp
#ifndef SECRETS_H
#define SECRETS_H
#define WIFI_SSID "Your_Network_Name"
#define WIFI_PASS "Your_WiFi_Password"
#endif
```

**What this does:**
- Creates a configuration file for WiFi credentials
- The ESP32 firmware will use these credentials to connect to your network
- Replace the placeholder values with your actual WiFi network name and password

---

### ROS2 WORKSPACE BUILD

#### Terminal: SSH to Rock64
**Location:** Rock64 SBC

```bash
# SSH into Rock64
ssh rock64@192.168.1.139

# Navigate to project directory
cd /opt/rock64-robot

# Source ROS2 environment
source /opt/ros/humble/setup.bash

# Navigate to host workspace
cd host_ws

# Build the ROS2 workspace
colcon build --symlink-install

# Source the workspace
source install/setup.bash
```

**What this does:**
- Connects to the Rock64 SBC
- Sources the ROS2 Humble environment variables
- Changes to the ROS2 workspace directory
- Builds all ROS2 packages in the workspace
- Uses symlink-install for faster development iterations
- Sources the built workspace to make packages available

#### Terminal: Windows PowerShell (Alternative)
**Location:** Development machine

```powershell
# Navigate to project directory
cd C:\Projects\Tank-Robot\Tank-robot

# Run Windows build script
powershell -ExecutionPolicy Bypass -File .\scripts\build_host_windows.ps1

# If Visual Studio environment variables are not set, the script will:
# 1. Automatically load VsDevCmd.bat
# 2. Source ROS2 environment
# 3. Run colcon build --symlink-install
```

**What this does:**
- Builds the ROS2 workspace on Windows
- Automatically handles Visual Studio toolchain setup
- Sources the ROS2 environment (if installed on Windows)
- Builds all packages with symlink-install for development

---

### HARDWARE PERMISSIONS CONFIGURATION

#### Terminal: SSH to Rock64 (as root)
**Location:** Rock64 SBC

```bash
# SSH into Rock64
ssh rock64@192.168.1.139

# Add rock64 user to dialout group for serial port access
sudo usermod -a -G dialout rock64

# Add rock64 user to i2c group for I2C sensor access
sudo usermod -a -G i2c rock64

# Add rock64 user to gpio group for GPIO access
sudo usermod -a -G gpio rock64

# Create udev rule for STM32 serial port
sudo nano /etc/udev/rules.d/99-rock64-robot.rules
```

**Add the following content to the udev rules file:**
```
# STM32 serial port
SUBSYSTEM=="tty", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="5740", SYMLINK+="rock64_stm32", MODE="0666"

# ESP32 serial port
SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", SYMLINK+="esp32", MODE="0666"
```

```bash
# Reload udev rules
sudo udevadm control --reload-rules
sudo udevadm trigger

# Log out and log back in for group changes to take effect
exit
```

**What this does:**
- Adds the rock64 user to groups required for hardware access
- Creates udev rules to give consistent names to serial devices
- The STM32 will appear as /dev/rock64_stm32 regardless of which USB port it's connected to
- Reloads the udev system to apply the new rules
- Requires logout/login for group membership changes to take effect

---

### SYSTEM LAUNCH & OPERATION

#### Terminal: SSH to Rock64
**Location:** Rock64 SBC

```bash
# SSH into Rock64
ssh rock64@192.168.1.139

# Navigate to project directory
cd /opt/rock64-robot

# Source ROS2 environment
source /opt/ros/humble/setup.bash

# Source workspace
source host_ws/install/setup.bash

# Launch the robot system (default legacy bridge mode)
ros2 launch robot_bringup rock64_bringup.launch.py

# Launch with micro-ROS mode (when STM32 firmware supports micro-ROS)
ros2 launch robot_bringup rock64_bringup.launch.py use_micro_ros:=true use_legacy_bridges:=false

# Launch with camera bridge enabled
ros2 launch robot_bringup rock64_bringup.launch.py use_camera_bridge:=true

# Launch with motor bringup test (low-speed motor test sequence)
ros2 launch robot_bringup rock64_bringup.launch.py use_micro_ros:=true run_motor_bringup_test:=true
```

**What this does:**
- Connects to the Rock64 and sources the necessary ROS2 environments
- Launches the complete robot system including:
  - PS5 controller bridge
  - STM32 serial bridge (or micro-ROS agent)
  - ESP32 camera bridge (if enabled)
  - All sensor processing nodes
- Different launch modes for different firmware configurations
- Motor bringup test for initial motor testing

#### Terminal: SSH to Rock64 (Systemd Service)
**Location:** Rock64 SBC

```bash
# SSH into Rock64
ssh rock64@192.168.1.139

# Start the robot systemd service
sudo systemctl start rock64-robot.service

# Enable auto-start on boot
sudo systemctl enable rock64-robot.service

# Check service status
sudo systemctl status rock64-robot.service

# View service logs
journalctl -u rock64-robot.service -f

# Restart the service
sudo systemctl restart rock64-robot.service

# Stop the service
sudo systemctl stop rock64-robot.service
```

**What this does:**
- Manages the robot system as a systemd service
- Enables automatic startup on boot
- Provides service management (start, stop, restart)
- Allows viewing logs and monitoring service status

---

### VERIFICATION & TESTING

#### Terminal: SSH to Rock64
**Location:** Rock64 SBC

```bash
# SSH into Rock64
ssh rock64@192.168.1.139

# Source ROS2 environment
source /opt/ros/humble/setup.bash
source /opt/rock64-robot/host_ws/install/setup.bash

# List all active ROS2 topics
ros2 topic list

# List all active ROS2 nodes
ros2 node list

# Monitor /cmd_vel topic (should see commands from PS5 controller)
ros2 topic echo /cmd_vel

# Monitor encoder ticks from STM32
ros2 topic echo /stm32/encoder_ticks

# Monitor STM32 bridge status
ros2 topic echo /stm32/bridge_alive

# Monitor IMU data
ros2 topic echo /imu/data

# Monitor camera images (visual)
ros2 run image_tools showimage --ros-args -r image:=/camera/image_raw
```

**What this does:**
- Verifies that the ROS2 system is functioning correctly
- Shows all active communication topics
- Displays all running nodes
- Monitors command flow from controller to motors
- Checks sensor data flow from encoders and IMU
- Displays camera feed for visual verification

#### Terminal: SSH to Rock64 (Hardware Tests)
**Location:** Rock64 SBC

```bash
# SSH into Rock64
ssh rock64@192.168.1.139

# Check STM32 serial port connection
ls -l /dev/rock64_stm32

# Test STM32 communication (should see heartbeat data)
cat /dev/rock64_stm32

# Check ESP32 WiFi connection
ping 192.168.1.125

# Test ESP32 camera stream
curl http://192.168.1.125:81/stream

# Or open in browser on development machine
# Navigate to: http://192.168.1.125:81/stream
```

**What this does:**
- Verifies hardware connections at the operating system level
- Tests serial communication with STM32
- Tests network connectivity to ESP32
- Verifies camera stream is accessible
- Provides basic hardware-level diagnostics

#### Terminal: SSH to Rock64 (Teleop Test)
**Location:** Rock64 SBC

```bash
# SSH into Rock64
ssh rock64@192.168.1.139

# Source ROS2 environment
source /opt/ros/humble/setup.bash
source /opt/rock64-robot/host_ws/install/setup.bash

# Launch keyboard teleop for testing (alternative to PS5)
ros2 run robot_teleop keyboard_teleop

# Use keyboard controls:
# w/i: forward
# s/k: backward
# a/j: left
# d/l: right
# space: stop
```

**What this does:**
- Provides keyboard-based teleop for testing without PS5 controller
- Useful for initial testing when PS5 controller is not available
- Sends velocity commands to /cmd_vel topic
- Same command interface as PS5 controller

---

### GAZEBO SIMULATION

#### Terminal: SSH to Rock64
**Location:** Rock64 SBC

```bash
# SSH into Rock64
ssh rock64@192.168.1.139

# Source ROS2 environment
source /opt/ros/humble/setup.bash
source /opt/rock64-robot/host_ws/install/setup.bash

# Install Gazebo dependencies (if not already installed)
sudo apt-get update
sudo apt-get install -y ros-humble-ros-gz

# Launch Gazebo simulation with ROS bridge
ros2 launch robot_bringup gazebo_harmonic.launch.py

# Launch Gazebo with telemetry overlays (RViz)
ros2 launch robot_bringup gazebo_telemetry.launch.py
```

**What this does:**
- Installs Gazebo simulation dependencies for ROS2
- Launches a simulated tank world with ROS/Gazebo bridge
- Topics /cmd_vel and /odom are bridged between ROS and Gazebo
- Telemetry launch adds RViz for visualization
- Useful for testing software without hardware

---

### DIAGNOSTICS & DEBUGGING

#### Terminal: SSH to Rock64
**Location:** Rock64 SBC

```bash
# SSH into Rock64
ssh rock64@192.168.1.139

# Check system resource usage
htop

# Check disk usage
df -h

# Check ROS2 topic bandwidth
ros2 topic bw /cmd_vel

# Check ROS2 topic latency
ros2 topic latency /cmd_vel

# Check ROS2 topic info
ros2 topic info /cmd_vel

# Check node information
ros2 node info /ps5_ros_bridge

# Run ROS2 diagnostic aggregator
ros2 run rqt_console rqt_console

# Run ROS2 runtime monitor
ros2 run rqt_runtime_monitor rqt_runtime_monitor
```

**What this does:**
- Monitors system resources (CPU, memory, etc.)
- Checks disk space availability
- Measures ROS2 topic bandwidth and latency
- Provides detailed information about topics and nodes
- Launches graphical diagnostic tools for ROS2

#### Terminal: SSH to Rock64 (Log Analysis)
**Location:** Rock64 SBC

```bash
# SSH into Rock64
ssh rock64@192.168.1.139

# View system logs
sudo journalctl -xe

# View kernel logs
dmesg

# View ROS2 logs (if using ros2 bag)
ros2 bag info <bag_file>

# Play back ros2 bag
ros2 bag play <bag_file>

# Record ros2 bag
ros2 bag record -o my_bag /cmd_vel /imu/data /camera/image_raw
```

**What this does:**
- Reviews system-level logs for errors
- Checks kernel messages for hardware issues
- Analyzes ROS2 bag recordings
- Records sensor data for offline analysis
- Plays back recorded data for debugging

---

### UPDATE & MAINTENANCE

#### Terminal: SSH to Rock64
**Location:** Rock64 SBC

```bash
# SSH into Rock64
ssh rock64@192.168.1.139

# Navigate to project directory
cd /opt/rock64-robot

# Pull latest changes from repository
git pull origin main

# Rebuild ROS2 workspace after updates
cd host_ws
colcon build --symlink-install

# Source workspace
source install/setup.bash

# Restart robot service
sudo systemctl restart rock64-robot.service
```

**What this does:**
- Updates the codebase to the latest version
- Rebuilds the ROS2 workspace with changes
- Restarts the robot service with updated software
- Ensures the system is running the latest code

#### Terminal: Windows PowerShell (STM32 Update)
**Location:** Development machine

```powershell
# Navigate to project directory
cd C:\Projects\Tank-Robot\Tank-robot

# Pull latest changes
git pull origin main

# Build and flash updated STM32 firmware
powershell -ExecutionPolicy Bypass -File .\scripts\flash_stm32_windows.ps1 -Build -Verify
```

**What this does:**
- Updates the STM32 firmware to the latest version
- Builds and flashes the updated firmware
- Verifies successful programming

#### Terminal: Windows PowerShell (ESP32 Update)
**Location:** Development machine

```powershell
# Navigate to ESP32 directory
cd C:\Projects\Tank-Robot\Tank-robot\firmware\esp32_sensors

# Pull latest changes
cd C:\Projects\Tank-Robot\Tank-robot
git pull origin main

# Build and flash updated ESP32 firmware
cd firmware\esp32_sensors
pio run -e esp32cam -t upload
```

**What this does:**
- Updates the ESP32 firmware to the latest version
- Builds and flashes the updated firmware via PlatformIO

---

### EMERGENCY PROCEDURES

#### Terminal: SSH to Rock64 (Emergency Stop)
**Location:** Rock64 SBC

```bash
# SSH into Rock64
ssh rock64@192.168.1.139

# IMMEDIATE MOTOR STOP - Stop all robot motion
ros2 topic pub --once /cmd_vel geometry_msgs/Twist "{linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}"

# Stop the robot service
sudo systemctl stop rock64-robot.service

# Kill all ROS2 nodes
killall -9 ros2
killall -9 micro_ros_agent
```

**What this does:**
- Immediately sends zero-velocity command to stop motors
- Stops the robot systemd service
- Force-kills all ROS2 processes as emergency measure
- Use only in emergency situations

#### Terminal: SSH to Rock64 (System Recovery)
**Location:** Rock64 SBC

```bash
# SSH into Rock64
ssh rock64@192.168.1.139

# Reboot the Rock64
sudo reboot

# Power cycle the entire robot system
sudo poweroff

# Then manually power cycle and restart
```

**What this does:**
- Reboots the Rock64 SBC
- Powers off the entire system
- Use for system-level recovery when software recovery fails

---

## 1. HARDWARE INFRASTRUCTURE

### 1.1 Core Computing Hardware
- [ ] **Rock64 SBC**
  - [ ] Board powered and booting from eMMC/SD card
  - [ ] Ubuntu 22.04 (Humble)
  - [ ] SSH access configured and working @192.168.1.139 
  - [ ] User permissions configured (sudo access for setup)
  - [ ] Sufficient storage available (>16GB free)
  - [ ] CPU monitoring and thermal management functional

- [ ] **STM32F407 Motor Controller**
  - [ ] STM32F407VGTx chip verified
  - [ ] Power supply stable (5V, sufficient current for motors)
  - [ ] SWD programming header accessible
  - [ ] Status LEDs functional (power, activity)
  - [ ] Clock configuration verified (168MHz system clock)
  - [ ] Boot mode configured correctly

- [ ] **ESP32-S3 Camera Node**
  - [ ] ESP32-S3 WROOM module verified
  - [ ] USB-C connection to Rock64 established
  - [ ] Camera module (OV2640/OV5640) connected
  - [ ] PSRAM detection verified (if applicable)
  - [ ] Boot mode functional

### 1.2 Mechanical Systems
- [ ] **Tank Chassis**
  - [ ] Hiwonder tank chassis assembled
  - [ ] Both track tensioners adjusted properly
  - [ ] Track alignment verified (no binding)
  - [ ] All mechanical fasteners secured
  - [ ] Center of gravity balanced
  - [ ] Ground clearance adequate for terrain

- [ ] **Drive Motors**
  - [ ] Left motor connected to STM32 TIM3_CH1 (PA6)
  - [ ] Right motor connected to STM32 TIM3_CH2 (PA7)
  - [ ] Motor driver power connections verified
  - [ ] Motor direction wiring confirmed (forward/reverse)
  - [ ] Motor current draw within specifications
  - [ ] Mechanical coupling to drive sprockets secure

- [ ] **Encoders**
  - [ ] Left encoder installed and functional
  - [ ] Right encoder installed and functional
  - [ ] Encoder signals connected to appropriate STM32 pins
  - [ ] Encoder resolution verified (ticks per revolution)
  - [ ] Encoder noise filtering implemented
  - [ ] Encoder telemetry formatted correctly (ENC:123,456)

### 1.3 Power Systems
- [ ] **Primary Power**
  - [ ] Battery pack voltage nominal (e.g., 7.4V LiPo)
  - [ ] Battery capacity sufficient for runtime requirements
  - [ ] Battery management system (BMS) functional
  - [ ] Power switch accessible and labeled
  - [ ] Low-voltage cutoff configured

- [ ] **Power Distribution**
  - [ ] 5V regulator for STM32 stable
  - [ ] 3.3V regulator for ESP32 stable
  - [ ] Motor power separate from logic power
  - [ ] Fuse protection installed where required
  - [ ] Power wiring gauge appropriate for current draw
  - [ ] Power capacitors installed for motor noise suppression

### 1.4 Sensor Hardware
- [ ] **IMU (MPU6050)**
  - [ ] MPU6050 connected to I2C1 (SCL: PB6, SDA: PB7)
  - [ ] I2C address verified (0x68)
  - [ ] Accelerometer calibration performed
  - [ ] Gyroscope calibration performed
  - [ ] Sensor orientation relative to robot frame documented
  - [ ] Data rate configured appropriately

- [ ] **Camera System**
  - [ ] OV2640/OV5640 camera module connected to ESP32
  - [ ] Camera focus adjusted
  - [ ] Camera mounting secure and vibration-damped
  - [ ] Field of view appropriate for navigation
  - [ ] Lighting conditions considered for operating environment

### 1.5 User Interface Hardware
- [ ] **PS5 Controller**
  - [ ] DualSense controller paired via Bluetooth
  - [ ] USB fallback mode tested
  - [ ] Controller charging functional
  - [ ] Button mapping verified in ROS2 node
  - [ ] Deadman switch mechanism configured

- [ ] **Emergency Stop**
  - [ ] Physical emergency stop button installed
  - [ ] E-stop button wired to motor power cutoff
  - [ ] E-stop button accessible during operation
  - [ ] E-stop status monitored in software
  - [ ] Reset procedure documented

---

## 2. COMMUNICATION SYSTEMS

### 2.1 Serial Communication (UART)
- [ ] **STM32 Serial Port**
  - [ ] USB-UART adapter connected to Rock64
  - [ ] udev rule configured for /dev/rock64_stm32
  - [ ] Baud rate set to 115200 (8N1)
  - [ ] USART2_TX: PA2, USART2_RX: PA3 verified
  - [ ] Serial permissions configured for rock64 user
  - [ ] Serial communication tested bidirectional

- [ ] **ESP32 Serial Port**
  - [ ] USB-C serial connection functional
  - [ ] ESP32 upload mode accessible (BOOT + EN/RST)
  - [ ] Serial monitor working at 115200 baud
  - [ ] Device permissions configured

### 2.2 Network Communication (WiFi)
- [ ] **ESP32 WiFi Configuration**
  - [ ] WiFi credentials configured in secrets.h
  - [ ] ESP32 connects to 2.4GHz network
  - [ ] Static IP assigned (192.168.1.125 or similar)
  - [ ] WiFi signal strength adequate (> -70dBm)
  - [ ] WiFi reconnection logic implemented
  - [ ] MAC address filtering configured (if required)

- [ ] **Rock64 Network Configuration**
  - [ ] WiFi adapter configured (if using WiFi)
  - [ ] Ethernet connection tested (if using wired)
  - [ ] Network interface stable
  - [ ] Firewall rules allow required ports
  - [ ] Network latency acceptable (<50ms)

### 2.3 I2C Communication
- [ ] **STM32 I2C Bus**
  - [ ] I2C1 initialized at 100kHz
  - [ ] Pull-up resistors installed on SCL/SDA
  - [ ] MPU6050 responds to I2C ping
  - [ ] I2C error handling implemented
  - [ ] I2C bus arbitration working

### 2.4 USB Communication
- [ ] **USB Hub**
  - [ ] USB hub powered and connected to Rock64
  - [ ] ST-Link V2/V3 connected via hub
  - [ ] ESP32 connected via hub
  - [ ] PS5 controller dongle connected (if using)
  - [ ] USB current limits not exceeded
  - [ ] USB device enumeration reliable

- [ ] **ST-Link Programming**
  - [ ] ST-Link drivers installed on development host
  - [ ] ST-Link detected by lsusb
  - [ ] OpenOCD configuration tested
  - [ ] SWD connections secure (CLK, DIO, GND)
  - [ ] Programming speed appropriate

---

## 3. FIRMWARE & SOFTWARE DEPENDENCIES

### 3.1 STM32 Firmware
- [ ] **Build Environment**
  - [ ] ARM GCC toolchain installed (gcc-arm-none-eabi)
  - [ ] CMake installed (version >= 3.15)
  - [ ] STM32CubeMX installed (for code generation)
  - [ ] STM32 HAL library included
  - [ ] Build system working (CMakeLists.txt)

- [ ] **Firmware Components**
  - [ ] Motor control TIM3 configured (1kHz PWM)
  - [ ] UART2 configured for micro-ROS/legacy bridge
  - [ ] I2C1 configured for MPU6050
  - [ ] GPIO configured for motor direction pins
  - [ ] FreeRTOS kernel integrated
  - [ ] micro-ROS client library integrated (optional)

- [ ] **Firmware Features**
  - [ ] Motor PWM generation working
  - [ ] Motor direction control working
  - [ ] Encoder reading implemented
  - [ ] IMU data reading implemented
  - [ ] Serial communication protocol implemented
  - [ ] Watchdog timer configured
  - [ ] Safety timeout implemented (300ms command timeout)

- [ ] **Firmware Build & Flash**
  - [ ] Firmware builds without errors
  - [ ] Firmware flashes successfully via ST-Link
  - [ ] Flash verification passes
  - [ ] Firmware boots correctly on power-up
  - [ ] Firmware version tracking implemented

### 3.2 ESP32 Firmware
- [ ] **Build Environment**
  - [ ] PlatformIO installed
  - [ ] ESP32 toolchain installed
  - [ ] Arduino framework configured
  - [ ] ESP32 camera library installed
  - [ ] Build system working (platformio.ini)

- [ ] **Firmware Components**
  - [ ] Camera initialization working
  - [ ] MJPEG HTTP server implemented
  - [ ] WiFi station mode configured
  - [ ] HTTP server listening on port 81
  - [ ] Image compression configured (JPEG quality 12)
  - [ ] Frame rate appropriate (15-30 FPS)

- [ ] **Firmware Features**
  - [ ] Camera captures images successfully
  - [ ] MJPEG stream accessible via HTTP
  - [ ] WiFi auto-connect on boot
  - [ ] Error handling for camera failures
  - [ ] Status indicators implemented

- [ ] **Firmware Build & Flash**
  - [ ] Firmware builds without errors
  - [ ] Firmware uploads successfully
  - [ ] Firmware boots correctly
  - [ ] WiFi connection established on boot
  - [ ] Camera stream accessible

### 3.3 ROS2 Environment
- [ ] **ROS2 Installation**
  - [ ] ROS2 Humble (Ubuntu 22.04) or Jazzy (Ubuntu 24.04) installed
  - [ ] ROS2 environment sourcing working
  - [ ] colcon build tool installed
  - [ ] ROS2 workspace structure correct (host_ws)
  - [ ] Python 3 dependencies installed

- [ ] **ROS2 Packages**
  - [ ] robot_bringup package builds
  - [ ] robot_drivers package builds
  - [ ] robot_teleop package builds
  - [ ] ros_robot_controller package builds
  - [ ] ros_robot_controller_msgs package builds
  - [ ] All package dependencies satisfied

- [ ] **ROS2 Configuration**
  - [ ] ROS_DOMAIN_ID set to 42
  - [ ] RMW_IMPLEMENTATION set to rmw_fastrtps_cpp
  - [ ] ROBOT_NAMESPACE set to rock64_1
  - [ ] QoS profiles configured appropriately
  - [ ] ROS2 environment variables persistent

---

## 4. ROS2 NODES & BRIDGES

### 4.1 Launch System
- [ ] **rock64_bringup.launch.py**
  - [ ] Launch file syntax valid
  - [ ] Preflight checks implemented
  - [ ] Launch arguments documented
  - [ ] Conditional node loading working
  - [ ] Error handling implemented
  - [ ] Launch time validation functional

- [ ] **Launch Modes**
  - [ ] Legacy bridge mode tested (use_legacy_bridges:=true)
  - [ ] micro-ROS mode tested (use_micro_ros:=true)
  - [ ] Mixed mode validation working
  - [ ] Camera bridge mode tested
  - [ ] Motor bringup test mode functional

### 4.2 Driver Nodes
- [ ] **stm32_serial_bridge**
  - [ ] Serial port connection working
  - [ ] Baud rate configured correctly
  - [ ] Command timeout implemented (0.25s)
  - [ ] Heartbeat monitoring working (0.5s timeout)
  - [ ] Encoder telemetry parsing functional
  - [ ] Diagnostics publishing working
  - [ ] Error handling implemented

- [ ] **stm32_binary_bridge** (alternative)
  - [ ] Binary protocol implemented
  - [ ] Serial port connection working
  - [ ] Command parsing functional
  - [ ] Error handling implemented

- [ ] **esp32_camera_bridge**
  - [ ] HTTP client working
  - [ ] MJPEG stream parsing functional
  - [ ] Image conversion to sensor_msgs/Image working
  - [ ] Camera IP parameter configurable
  - [ ] Stream recovery on disconnect implemented
  - [ ] Error handling implemented

- [ ] **ps5_ros_bridge**
  - [ ] PS5 controller detection working
  - [ ] Button mapping configured
  - [ ] Deadman switch implemented
  - [ ] /cmd_vel publishing working
  - [ ] Joy input smoothing implemented
  - [ ] Connection loss handling implemented

### 4.3 micro-ROS Integration
- [ ] **micro_ros_agent**
  - [ ] micro-ROS agent installed on Rock64
  - [ ] Agent launches correctly
  - [ ] Serial transport configured
  - [ ] Baud rate configured (115200)
  - [ ] Agent discovers STM32 client
  - [ ] Agent logs are accessible

- [ ] **STM32 micro-ROS Client**
  - [ ] micro-ROS library integrated
  - [ ] Client initializes correctly
  - [ ] /cmd_vel subscription working
  - [ ] Publisher nodes working
  - [ ] Memory usage within limits
  - [ ] Real-time constraints met

---

## 5. SYSTEM INTEGRATION

### 5.1 Hardware Integration
- [ ] **Power-on Sequence**
  - [ ] Power-up order documented
  - [ ] All components power on successfully
  - [ ] Boot times measured and acceptable
  - [ ] Power consumption within limits
  - [ ] Thermal management adequate

- [ ] **Mechanical Integration**
  - [ ] All components securely mounted
  - [ ] Cable routing clean and secured
  - [ ] Strain relief installed on connectors
  - [ ] Vibrations dampened appropriately
  - [ ] Weight distribution balanced

### 5.2 Software Integration
- [ ] **Startup Sequence**
  - [ ] Systemd service configured
  - [ ] ROS2 workspace sourced automatically
  - [ ] Launch file starts on boot
  - [ ] All nodes initialize correctly
  - [ ] Dependencies between nodes resolved
  - [ ] Startup time acceptable (<30s)

- [ ] **Runtime Integration**
  - [ ] All ROS2 topics visible
  - [ ] Topic data flow verified
  - [ ] Node communication working
  - [ ] CPU usage acceptable
  - [ ] Memory usage acceptable
  - [ ] No resource conflicts

### 5.3 Communication Integration
- [ ] **End-to-end Communication**
  - [ ] PS5 controller commands reach STM32
  - [ ] STM32 executes motor commands
  - [ ] Encoder data returns to Rock64
  - [ ] IMU data published to ROS2
  - [ ] Camera stream accessible
  - [ ] Latencies within specifications

- [ ] **Error Recovery**
  - [ ] Serial reconnection working
  - [ ] WiFi reconnection working
  - [ ] Node restart on crash
  - [ ] Watchdog recovery functional
  - [ ] Graceful degradation implemented

---

## 6. SAFETY SYSTEMS

### 6.1 Hardware Safety
- [ ] **Emergency Stop**
  - [ ] Physical E-stop button cuts motor power
  - [ ] E-stop status monitored in software
  - [ ] E-stop reset procedure safe
  - [ ] E-stop tested under load

- [ ] **Power Safety**
  - [ ] Reverse polarity protection
  - [ ] Over-current protection
  - [ ] Over-voltage protection
  - [ ] Under-voltage cutoff
  - [ ] Thermal protection

### 6.2 Software Safety
- [ ] **Watchdog Systems**
  - [ ] STM32 hardware watchdog configured
  - [ ] ROS2 node watchdog implemented
  - [ ] Communication timeout (300ms)
  - [ ] Heartbeat monitoring (500ms)
  - [ ] Watchdog recovery tested

- [ ] **Command Safety**
  - [ ] Command validation implemented
  - [ ] Rate limiting on commands
  - [ ] Velocity limits enforced
  - [ ] Acceleration limits enforced
  - [ ] Deadman switch functional

- [ ] **Fail-safe Behavior**
  - [ ] Motors stop on communication loss
  - [ ] Safe state defined for all failures
  - [ ] Recovery procedures documented
  - [ ] Fail-safe tested comprehensively

---

## 7. CONFIGURATION & CALIBRATION

### 7.1 Motor Configuration
- [ ] **PWM Calibration**
  - [ ] PWM frequency set (1kHz)
  - [ ] PWM range configured (0-255 or 0-1000)
  - [ ] Deadband compensation implemented
  - [ ] Motor direction verified
  - [ ] Motor response linearized

- [ ] **Velocity Control**
  - [ ] Max linear speed configured (0.6 m/s)
  - [ ] Max angular speed configured (1.8 rad/s)
  - [ ] Track width parameter set (0.194 m)
  - [ ] Differential drive kinematics verified
  - [ ] Slew rate limiting configured

### 7.2 Sensor Calibration
- [ ] **IMU Calibration**
  - [ ] Accelerometer bias removed
  - [ ] Gyroscope bias removed
  - [ ] Sensor orientation calibrated
  - [ ] Temperature compensation applied
  - [ ] Noise filtering configured

- [ ] **Encoder Calibration**
  - [ ] Ticks per revolution measured
  - [ ] Wheel circumference calculated
  - [ ] Encoder offset removed
  - [ ] Encoder debounce implemented
  - [ ] Odometry calculations verified

### 7.3 Camera Configuration
- [ ] **Image Settings**
  - [ ] Resolution set (640x480 VGA)
  - [ ] Frame rate configured (15-30 FPS)
  - [ ] JPEG quality set (12)
  - [ ] White balance configured
  - [ ] Exposure settings appropriate

### 7.4 Network Configuration
- [ ] **IP Addressing**
  - [ ] ESP32 static IP assigned (192.168.1.125)
  - [ ] Rock64 IP address stable
  - [ ] DNS configuration working
  - [ ] Network topology documented
  - [ ] Firewall rules configured

---

## 8. TESTING & VERIFICATION

### 8.1 Unit Testing
- [ ] **Motor Control**
  - [ ] Left motor forward/reverse tested
  - [ ] Right motor forward/reverse tested
  - [ ] Motor speed control verified
  - [ ] Motor response time measured
  - [ ] Motor stall protection tested

- [ ] **Sensor Testing**
  - [ ] IMU data accuracy verified
  - [ ] Encoder counts verified
  - [ ] Camera image quality verified
  - [ ] Sensor noise measured
  - [ ] Sensor refresh rate measured

- [ ] **Communication Testing**
  - [ ] Serial reliability tested
  - [ ] WiFi reliability tested
  - [ ] I2C reliability tested
  - [ ] ROS2 topic reliability tested
  - [ ] Error injection testing performed

### 8.2 Integration Testing
- [ ] **Teleop Testing**
  - [ ] PS5 controller drives robot forward
  - [ ] PS5 controller drives robot backward
  - [ ] PS5 controller turns robot left
  - [ ] PS5 controller turns robot right
  - [ ] Combined linear/angular motion tested
  - [ ] Deadman switch tested

- [ ] **Autonomous Testing**
  - [ ] /cmd_vel commands executed correctly
  - [ ] Odometry published accurately
  - [ ] Sensor fusion working
  - [ ] Navigation stack integration (if applicable)
  - [ ] Obstacle avoidance tested (if applicable)

### 8.3 Performance Testing
- [ ] **Latency Testing**
  - [ ] Command-to-motor latency <10ms
  - [ ] Camera latency <100ms
  - [ ] Sensor latency <50ms
  - [ ] End-to-end latency measured

- [ ] **Stress Testing**
  - [ ] Continuous operation tested (1 hour+)
  - [ ] Battery life measured
  - [ ] Thermal performance verified
  - [ ] Memory leak testing performed
  - [ ] CPU load testing performed

---

## 9. DEPLOYMENT & OPERATIONS

### 9.1 Deployment
- [ ] **Rock64 Setup**
  - [ ] Repository cloned to /opt/rock64-robot
  - [ ] rock64_setup.sh script executed
  - [ ] ROS2 workspace built successfully
  - [ ] Systemd service installed
  - [ ] Auto-start on boot enabled
  - [ ] Deployment verified

- [ ] **Remote Access**
  - [ ] SSH access configured
  - [ ] SSH keys exchanged
  - [ ] SFTP access working
  - [ ] Remote development environment setup
  - [ ] Network security configured

### 9.2 Monitoring
- [ ] **System Monitoring**
  - [ ] CPU monitoring implemented
  - [ ] Memory monitoring implemented
  - [ ] Storage monitoring implemented
  - [ ] Temperature monitoring implemented
  - [ ] Power monitoring implemented
  - [ ] Network monitoring implemented

- [ ] **ROS2 Monitoring**
  - [ ] Topic monitoring working
  - [ ] Node monitoring working
  - [ ] Diagnostic aggregation working
  - [ ] Log collection implemented
  - [ ] Performance metrics collected

### 9.3 Maintenance
- [ ] **Backup Procedures**
  - [ ] Firmware backup procedure
  - [ ] Configuration backup procedure
  - [ ] Data backup procedure
  - [ ] Recovery procedures documented
  - [ ] Backup automation implemented

- [ ] **Update Procedures**
  - [ ] Firmware update procedure
  - [ ] Software update procedure
  - [ ] Configuration update procedure
  - [ ] Rollback procedures documented
  - [ ] Update testing procedure

---

## 10. DOCUMENTATION

### 10.1 System Documentation
- [ ] **Architecture Documentation**
  - [ ] System topology documented
  - [ ] Communication protocols documented
  - [ ] Data flow documented
  - [ ] Component interactions documented
  - [ ] Architecture diagrams created

- [ ] **Configuration Documentation**
  - [ ] Hardware configuration documented
  - [ ] Software configuration documented
  - [ ] Network configuration documented
  - [ ] Parameter files documented
  - [ ] Environment variables documented

### 10.2 Operational Documentation
- [ ] **User Documentation**
  - [ ] Quick start guide created
  - [ ] Operation manual written
  - [ ] Troubleshooting guide created
  - [ ] Safety procedures documented
  - [ ] FAQ created

- [ ] **Developer Documentation**
  - [ ] Build instructions written
  - [ ] Flashing guide completed
  - [ ] API documentation created
  - [ ] Code comments maintained
  - [ ] Development workflow documented

### 10.3 Maintenance Documentation
- [ ] **Maintenance Procedures**
  - [ ] Routine maintenance schedule
  - [ ] Calibration procedures
  - [ ] Testing procedures
  - [ ] Repair procedures
  - [ ] Replacement procedures

---

## 11. ENDPOINTS & INTERFACES

### 11.1 ROS2 Topics
- [ ] **Control Topics**
  - [ ] /cmd_vel (geometry_msgs/Twist) - Subscribed by STM32
  - [ ] /tracks/left_cmd - Left track command
  - [ ] /tracks/right_cmd - Right track command
  - [ ] Topic QoS configured appropriately
  - [ ] Topic remapping documented

- [ ] **Sensor Topics**
  - [ ] /stm32/encoder_ticks (std_msgs/Int32MultiArray)
  - [ ] /stm32/bridge_alive (std_msgs/Bool)
  - [ ] /stm32/diagnostics (diagnostic_msgs/DiagnosticArray)
  - [ ] /imu/data (sensor_msgs/Imu)
  - [ ] /camera/image_raw (sensor_msgs/Image)
  - [ ] Topic publishing rates verified

- [ ] **Input Topics**
  - [ ] /joy (sensor_msgs/Joy) - PS5 controller input
  - [ ] Topic mapping verified
  - [ ] Deadman switch implemented

### 11.2 ROS2 Services
- [ ] **Control Services**
  - [ ] Emergency stop service (if implemented)
  - [ ] Reset odometry service (if implemented)
  - [ ] Calibrate sensors service (if implemented)
  - [ ] Service interfaces documented

### 11.3 ROS2 Parameters
- [ ] **Hardware Parameters**
  - [ ] Serial port configured
  - [ ] Baud rate configured
  - [ ] Camera IP configured
  - [ ] Motor limits configured
  - [ ] Safety timeouts configured
  - [ ] Parameter reload mechanism working

### 11.4 HTTP Endpoints
- [ ] **Camera Stream**
  - [ ] http://<esp32_ip>:81/stream accessible
  - [ ] MJPEG format verified
  - [ ] Stream authentication (if required)
  - [ ] Stream quality acceptable
  - [ ] Stream latency acceptable

---

## 12. PERMISSIONS & SECURITY

### 12.1 System Permissions
- [ ] **User Permissions**
  - [ ] rock64 user created
  - [ ] sudo access configured
  - [ ] Group memberships correct (dialout, i2c, gpio)
  - [ ] Home directory permissions correct
  - [ ] SSH access configured

- [ ] **Device Permissions**
  - [ ] /dev/rock64_stm32 permissions (udev rule)
  - [ ] /dev/ttyUSB* permissions
  - [ ] /dev/i2c-* permissions
  - [ ] GPIO permissions
  - [ ] USB device permissions

### 12.2 Network Security
- [ ] **WiFi Security**
  - [ ] WPA2-PSK configured
  - [ ] Network encryption enabled
  - [ ] MAC address filtering (optional)
  - [ ] Guest network isolation (if applicable)
  - [ ] WiFi credentials secured

- [ ] **Firewall Configuration**
  - [ ] ufw enabled
  - [ ] Required ports open (SSH, ROS2, camera)
  - [ ] Unnecessary ports closed
  - [ ] IP filtering configured (if required)
  - [ ] Fail2ban configured (optional)

### 12.3 ROS2 Security
- [ ] **Domain ID Isolation**
  - [ ] ROS_DOMAIN_ID set to 42
  - [ ] Domain ID isolation verified
  - [ ] Cross-domain communication blocked
  - [ ] RMW implementation security reviewed

- [ ] **Node Security**
  - [ ] Node permissions reviewed
  - [ ] Topic access controls (if using ROS2 security)
  - [ ] Service access controls (if using ROS2 security)
  - [ ] Parameter access controls (if using ROS2 security)

---

## 13. PERFORMANCE OPTIMIZATION

### 13.1 Real-time Performance
- [ ] **STM32 Real-time**
  - [ ] FreeRTOS task priorities configured
  - [ ] Real-time constraints met
  - [ ] Interrupt latency measured
  - [ ] Context switch time measured
  - [ ] Real-time monitoring implemented

- [ ] **ROS2 Real-time**
  - [ ] RT kernel installed (if required)
  - [ ] Node priorities configured
  - [ ] Thread affinity set (if required)
  - [ ] Real-time QoS profiles used
  - [ ] Real-time performance verified

### 13.2 Resource Optimization
- [ ] **CPU Optimization**
  - [ ] CPU usage profiled
  - [ ] CPU hotspots identified
  - [ ] Algorithmic optimizations applied
  - [ ] Multithreading optimized
  - [ ] CPU scaling configured

- [ ] **Memory Optimization**
  - [ ] Memory usage profiled
  - [ ] Memory leaks eliminated
  - [ ] Stack sizes optimized
  - [ ] Heap usage optimized
  - [ ] Memory pools implemented (if applicable)

### 13.3 Network Optimization
- [ ] **Network Optimization**
  - [ ] Network latency optimized
  - [ ] Bandwidth usage optimized
  - [ ] Packet loss minimized
  - [ ] QoS tuning applied
  - [ ] Network compression (if applicable)

---

## 14. TROUBLESHOOTING CAPABILITIES

### 14.1 Diagnostic Tools
- [ ] **Hardware Diagnostics**
  - [ ] Serial monitoring tools available
  - [ ] I2C scanning tools available
  - [ ] GPIO testing tools available
  - [ ] Power monitoring tools available
  - [ ] Signal analysis tools available

- [ ] **Software Diagnostics**
  - [ ] ROS2 topic monitoring
  - [ ] ROS2 node monitoring
  - [ ] ROS2 service monitoring
  - [ ] System logs (journalctl)
  - [ ] Application logs

### 14.2 Debug Infrastructure
- [ ] **Debugging Tools**
  - [ ] STM32 debugging (ST-Link + OpenOCD)
  - [ ] ESP32 debugging (PlatformIO)
  - [ ] ROS2 debugging (rqt_console)
  - [ ] Python debugging (pdb)
  - [ ] Performance profiling

- [ ] **Debug Interfaces**
  - [ ] STM32 SWD access
  - [ ] ESP32 serial access
  - [ ] Rock64 SSH access
  - [ ] ROS2 introspection
  - [ ] Log aggregation

### 14.3 Common Issues
- [ ] **Known Issues Documented**
  - [ ] STM32 communication failures
  - [ ] ESP32 WiFi disconnections
  - [ ] ROS2 topic failures
  - [ ] Motor driver issues
  - [ ] Sensor noise issues
  - [ ] Known workarounds documented

---

## 15. FINAL ACCEPTANCE CRITERIA

### 15.1 Functional Requirements
- [ ] **Basic Mobility**
  - [ ] Robot moves forward on command
  - [ ] Robot moves backward on command
  - [ ] Robot turns left on command
  - [ ] Robot turns right on command
  - [ ] Robot stops on command
  - [ ] Robot combines motions smoothly

- [ ] **Teleoperation**
  - [ ] PS5 controller controls robot
  - [ ] Deadman switch functional
  - [ ] Control response smooth
  - [ ] Control latency acceptable
  - [ ] Controller reconnection works

- [ ] **Autonomous Operation**
  - [ ] /cmd_vel commands executed
  - [ ] Odometry published accurately
  - [ ] Sensor fusion working
  - [ ] Navigation stack functional (if applicable)
  - [ ] Autonomous behaviors tested

### 15.2 Non-Functional Requirements
- [ ] **Reliability**
  - [ ] System uptime > 95%
  - [ ] Mean time between failures > 4 hours
  - [ ] Automatic recovery functional
  - [ ] Error handling comprehensive

- [ ] **Performance**
  - [ ] Command latency < 50ms
  - [ ] Camera latency < 150ms
  - [ ] Control loop rate > 20Hz
  - [ ] Battery life > 30 minutes

- [ ] **Safety**
  - [ ] Emergency stop functional
  - [ ] Watchdog systems functional
  - [ ] Fail-safe behaviors tested
  - [ ] Safety documentation complete

### 15.3 Documentation Requirements
- [ ] **Documentation Complete**
  - [ ] All checklists completed
  - [ ] All procedures documented
  - [ ] All configurations documented
  - [ ] All interfaces documented
  - [ ] Troubleshooting guide complete

---

## SIGN-OFF

**Project Lead:** ______________________ Date: ________

**Systems Engineer:** ______________________ Date: ________

**Safety Officer:** ______________________ Date: ________

**Test Engineer:** ______________________ Date: ________

---

## APPENDICES

### Appendix A: Pin Mapping Reference
- STM32 USART2_TX: PA2
- STM32 USART2_RX: PA3
- STM32 TIM3_CH1: PA6 (left motor PWM)
- STM32 TIM3_CH2: PA7 (right motor PWM)
- STM32 M1_F: PA0 (left motor forward)
- STM32 M1_B: PA1 (left motor reverse)
- STM32 M2_F: PA15 (right motor forward)
- STM32 M2_B: PB3 (right motor reverse)
- STM32 I2C1_SCL: PB6 (MPU6050 clock)
- STM32 I2C1_SDA: PB7 (MPU6050 data)

### Appendix B: Network Configuration Reference
- ESP32 IP: 192.168.1.125
- ESP32 Port: 81 (MJPEG stream)
- Rock64 IP: [configured during deployment]
- ROS Domain ID: 42
- ROS Namespace: rock64_1

### Appendix C: Safety Parameters Reference
- Command timeout: 300ms
- Heartbeat timeout: 500ms
- Watchdog timeout: [STM32-specific]
- Max linear speed: 0.6 m/s
- Max angular speed: 1.8 rad/s
- Motor PWM frequency: 1 kHz

### Appendix D: Command Reference
```bash
# Build STM32 firmware
cd firmware/stm32_chassis && cmake --build build

# Flash STM32 firmware
./scripts/flash_stm32.sh --build --verify

# Build ESP32 firmware
cd firmware/esp32_sensors && pio run -e esp32cam

# Flash ESP32 firmware
pio run -e esp32cam -t upload

# Build ROS2 workspace
cd host_ws && colcon build --symlink-install

# Launch robot system
ros2 launch robot_bringup rock64_bringup.launch.py

# Launch with micro-ROS
ros2 launch robot_bringup rock64_bringup.launch.py use_micro_ros:=true use_legacy_bridges:=false

# Launch with camera bridge
ros2 launch robot_bringup rock64_bringup.launch.py use_camera_bridge:=true
```

---

**Document Version:** 1.0  
**Last Updated:** 2026-07-29  
**Project:** Rock64 Ranger Tank Robot  
**Status:** Draft for Review
