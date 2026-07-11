# Flashing Guide — Rock64 Ranger

## Overview

This guide covers flashing firmware to all three hardware components:
1. **STM32F407** (Motor controller)
2. **ESP32-S3** (Camera node)
3. **Rock64** (ROS2 deployment)

---

## Prerequisites

### Common Requirements
- Ubuntu 24.04 (Jazzy) or Ubuntu 22.04 (Humble)
- ARM toolchain: `gcc-arm-none-eabi`
- Flashing tools: `stlink-tools`, `openocd`
- PlatformIO (for ESP32): `pip install platformio`

### Install Dependencies
```bash
sudo apt update
sudo apt install gcc-arm-none-eabi cmake stlink-tools openocd
pip install platformio
```

---

## 1. Flashing STM32F407

### Hardware Setup
1. Connect ST-Link V2/V3 to STM32F407 SWD header
2. Connect ST-Link to Rock64 via USB
3. Verify connection: `lsusb | grep ST-LINK`

### Build Firmware
```bash
cd firmware/stm32_chassis
cmake -B build -DCMAKE_TOOLCHAIN_FILE=cmake/stm32_toolchain.cmake
cmake --build build
```

### Flash Firmware
```bash
# Basic flash
cd ../..
./scripts/flash_stm32.sh --build

# Flash with verification
./scripts/flash_stm32.sh --build --verify

# Full chip erase before flash
./scripts/flash_stm32.sh --build --erase
```

### Manual Flashing (OpenOCD)
```bash
cd firmware/stm32_chassis
openocd -f ../scripts/openocd_stm32f407.cfg \
  -c "program build/rock64_ranger_fw.elf verify reset exit"
```

### Troubleshooting
- **ST-Link not detected**: Check USB permissions, try `sudo`
- **Flash fails**: Ensure ST-Link drivers are installed
- **Verification fails**: Check SWD connections, try slower clock speed

---

## 2. Flashing ESP32-S3

### Hardware Setup
1. Connect ESP32-S3 to Rock64 via USB-C
2. Put ESP32 in download mode (hold BOOT button, press EN/RST)
3. Verify connection: `ls /dev/ttyUSB*` or `ls /dev/ttyACM*`

### Build Firmware
```bash
cd firmware/esp32_sensors
pio run -e esp32cam
```

### Flash Firmware
```bash
# Flash to connected board
pio run -e esp32cam -t upload

# Flash with specific port
pio run -e esp32cam -t upload --upload-port /dev/ttyUSB0

# Monitor serial output
pio device monitor -p /dev/ttyUSB0 -b 115200
```

### Set WiFi Credentials
Create `firmware/esp32_sensors/include/secrets.h`:
```cpp
#ifndef SECRETS_H
#define SECRETS_H
#define WIFI_SSID "your_network_name"
#define WIFI_PASS "your_password"
#endif
```

Update `platformio.ini` to include:
```ini
build_flags =
  -DBOARD_HAS_PSRAM
  -DARDUINO_USB_MODE=1
  -DARDUINO_USB_CDC_ON_BOOT=1
  -Iinclude
```

### Troubleshooting
- **Port not found**: Check device permissions, try `sudo`
- **Upload fails**: Ensure ESP32 is in download mode
- **WiFi not connecting**: Verify SSID/password, check 2.4GHz support

---

## 3. Deploying to Rock64

### Initial Setup
```bash
# Clone repository to Rock64
git clone https://github.com/zixxenK/Tank-robot /opt/rock64-robot
cd /opt/rock64-robot

# Run setup script
sudo bash deployment/scripts/rock64_setup.sh --ros-distro auto
```

### Manual ROS2 Build
```bash
# Source ROS2 environment
source deployment/scripts/source_ros2_ws.sh

# Build workspace
cd ros2_ws
colcon build --symlink-install

# Source workspace
source install/setup.bash
```

### Start Robot
```bash
# Manual start
ros2 launch robot_bringup rock64_bringup.launch.py

# Or start systemd service
sudo systemctl start rock64-robot.service

# Check status
sudo systemctl status rock64-robot.service
```

### Systemd Service
```bash
# Enable auto-start on boot
sudo systemctl enable rock64-robot.service

# View logs
journalctl -u rock64-robot.service -f

# Restart service
sudo systemctl restart rock64-robot.service
```

---

## 4. Verification

### STM32 Verification
```bash
# Check serial port
ls -l /dev/rock64_stm32

# Test communication (should receive heartbeat)
cat /dev/rock64_stm32
```

### ESP32 Verification
```bash
# Check WiFi connection
ping <esp32_ip>

# Test MJPEG stream
curl http://<esp32_ip>:81/stream

# Or open in browser
firefox http://<esp32_ip>:81/stream
```

### ROS2 Verification
```bash
# Check topics
ros2 topic list

# Check /cmd_vel
ros2 topic echo /cmd_vel

# Check camera
ros2 topic echo /camera/image_raw

# Check nodes
ros2 node list
```

### Integration Test
```bash
# Start teleop
ros2 run robot_teleop keyboard_teleop

# Send command
# Should see motors respond and heartbeat in STM32 serial
```

---

## 5. Quick Reference

### STM32 Commands
```bash
# Build only
cd firmware/stm32_chassis && cmake --build build

# Flash only
./scripts/flash_stm32.sh

# Build and flash
./scripts/flash_stm32.sh --build
```

### ESP32 Commands
```bash
# Build only
cd firmware/esp32_sensors && pio run

# Flash only
pio run -t upload

# Build and flash
pio run -t upload
```

### ROS2 Commands
```bash
# Build workspace
cd ros2_ws && colcon build

# Source and launch
source install/setup.bash
ros2 launch robot_bringup rock64_bringup.launch.py
```

---

## 6. Safety Checks Before First Run

### Hardware Checks
- [ ] STM32 SWD connections secure
- [ ] STM32 power supply stable (5V)
- [ ] ESP32 USB-C connection secure
- [ ] Motor driver power connections verified
- [ ] Emergency stop button accessible

### Software Checks
- [ ] STM32 firmware builds without errors
- [ ] ESP32 firmware builds without errors
- [ ] ROS2 workspace builds without errors
- [ ] Serial port permissions correct
- [ ] WiFi credentials configured

### Communication Checks
- [ ] STM32 heartbeat received
- [ ] ESP32 MJPEG stream accessible
- [ ] ROS2 topics visible
- [ ] Motor commands acknowledged

### Safety Tests
- [ ] Motors stop when /cmd_vel stops
- [ ] Motors stop on heartbeat timeout
- [ ] Emergency stop button works
- [ ] Motors don't run on power-up

---

## 7. Common Issues

### STM32 Issues
**Issue**: ST-Link not detected
- **Solution**: Install `stlink-tools`, check USB permissions

**Issue**: Flash verification fails
- **Solution**: Check SWD connections, try `--erase` flag

**Issue**: No heartbeat from STM32
- **Solution**: Check UART baud rate, verify pin mapping

### ESP32 Issues
**Issue**: Upload fails
- **Solution**: Hold BOOT button, press EN/RST

**Issue**: WiFi won't connect
- **Solution**: Verify 2.4GHz support, check credentials

**Issue**: Camera stream not accessible
- **Solution**: Check ESP32 IP, verify camera initialization

### ROS2 Issues
**Issue**: colcon build fails
- **Solution**: Source ROS2 environment, check dependencies

**Issue**: Nodes can't communicate
- **Solution**: Check ROS_DOMAIN_ID, verify RMW implementation

**Issue**: Camera bridge crashes
- **Solution**: Check ESP32 connectivity, verify URL parameter

---

## 8. Development Workflow

### STM32 Development
```bash
# 1. Edit source files
vim firmware/stm32_chassis/Core/Src/main.c

# 2. Build
cd firmware/stm32_chassis && cmake --build build

# 3. Flash
./scripts/flash_stm32.sh

# 4. Test
# Monitor serial output
cat /dev/rock64_stm32
```

### ESP32 Development
```bash
# 1. Edit source files
vim firmware/esp32_sensors/src/main.cpp

# 2. Build and flash
cd firmware/esp32_sensors && pio run -t upload

# 3. Monitor
pio device monitor

# 4. Test
# Open camera stream in browser
```

### ROS2 Development
```bash
# 1. Edit source files
vim ros2_ws/src/robot_drivers/robot_drivers/stm32_serial_bridge.py

# 2. Build
cd ros2_ws && colcon build --symlink-install

# 3. Source
source install/setup.bash

# 4. Test
ros2 launch robot_bringup rock64_bringup.launch.py
```

---

## 9. Recovery Procedures

### STM32 Recovery
```bash
# If STM32 is bricked, try full chip erase
./scripts/flash_stm32.sh --erase

# If that fails, use ST-Link Utility
st-info --probe
st-flash erase
st-flash write build/rock64_ranger_fw.bin 0x8000000
```

### ESP32 Recovery
```bash
# If ESP32 won't boot, try erase flash
pio run -t erase

# Then reflash
pio run -t upload
```

### ROS2 Recovery
```bash
# If workspace is corrupted, clean build
cd ros2_ws
rm -rf build install log
colcon build --symlink-install
```

---

## 10. Advanced Configuration

### STM32 Clock Configuration
Edit `SystemClock_Config()` in `main.c` to adjust system clock speed.

### ESP32 Camera Settings
Edit camera configuration in `main.cpp`:
- Resolution: `config.frame_size`
- Quality: `config.jpeg_quality`
- Frame rate: Adjust via `config.xclk_freq_hz`

### ROS2 Parameters
Edit `ros2_ws/src/robot_bringup/config/rock64_hardware.yaml` for node parameters.

---

## Appendix: File Locations

| Component | Firmware Binary | Source Files |
|-----------|----------------|--------------|
| STM32 | `firmware/stm32_chassis/build/rock64_ranger_fw.elf` | `firmware/stm32_chassis/Core/` |
| ESP32 | `firmware/esp32_sensors/.pio/build/esp32cam/firmware.bin` | `firmware/esp32_sensors/src/` |
| ROS2 | `ros2_ws/install/` | `ros2_ws/src/` |

---

## Support

For issues:
1. Check hardware connections
2. Review this guide's troubleshooting section
3. Check logs: `journalctl -u rock64-robot.service -f`
4. Verify all communication protocols (see `docs/communication_protocols.md`)
