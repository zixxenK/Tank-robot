# HC-SR04 test checklist

This repository now contains the firmware and Rock64 transport path, but the
firmware must be flashed before the sensor is connected.

## Firmware validation

From an ARM toolchain environment:

```bash
cmake -S firmware/stm32_chassis -B firmware/stm32_chassis/build/rock64 \
  -DCMAKE_TOOLCHAIN_FILE=firmware/stm32_chassis/cmake/gcc-arm-none-eabi.cmake
cmake --build firmware/stm32_chassis/build/rock64
```

Flash only with the controller disconnected from the HC-SR04:

```bash
cmake --build firmware/stm32_chassis/build/rock64 --target flash
```

The image configures PC8 as the trigger output and PC9 as a rising/falling
edge input. The old PC8/PC9 servo configuration is not safe for this test.

## ROS validation

After flashing and wiring with power off:

```bash
cd ~/Tank-robot/host_ws
colcon build --symlink-install --packages-select robot_drivers robot_bringup
source install/setup.bash
ros2 launch robot_bringup rock64_bringup.launch.py \
  use_teleop:=false use_audio:=false \
  use_lidar:=true use_camera_bridge:=false use_usb_camera:=false
ros2 topic echo /ultrasonic/range
```

Expected topics are:

- `/ultrasonic/range` — HC-SR04 `sensor_msgs/Range`;
- `/scan` — synchronized STL-50B2 `sensor_msgs/LaserScan`;
- `/camera/image_raw` — ESP32 camera;
- `/camera/usb/image_raw` — USB webcam after the webcam node is enabled;
- `/stm32/imu`, `/stm32/odom`, and `/stm32/diagnostics` — STM32 data.

Keep the robot tracks raised and motion disabled during the first sensor test.
