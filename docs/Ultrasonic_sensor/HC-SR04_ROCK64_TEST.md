# HC-SR04 test checklist

This repository contains the firmware and Rock64 transport path. Verify the
controller image before connecting the sensor; do not assume that a previously
flashed board has the HC-SR04 image.

## Firmware validation

From the Rock64:

```bash
bash deployment/scripts/rock64_update_and_flash.sh
```

This is the only supported STM32 release path. It builds on the Rock64, flashes
through the Rock64-connected ST-Link, verifies readback, starts the image, and
runs the safe UART proof before any sensor or motor validation.

The image configures PC8 as the trigger output and PA12 as a rising/falling
edge input. The legacy PC8/PC9 servo configuration is not safe for this test.
HC-SR04 ECHO is a 5 V signal: use a resistor divider or level shifter unless
the complete PA12 input path on the exact controller board has been verified as
5 V tolerant.

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
ros2 topic echo /stm32/diagnostics
```

Expected topics are:

- `/ultrasonic/range` — HC-SR04 `sensor_msgs/Range`;
- `/scan` — synchronized STL-50B2 `sensor_msgs/LaserScan`;
- `/camera/image_raw` — ESP32 camera;
- `/camera/usb/image_raw` — USB webcam after the webcam node is enabled;
- `/stm32/imu`, `/stm32/odom`, and `/stm32/diagnostics` — STM32 data.
- The HC-SR04 status is included in `/stm32/diagnostics`; look for
  `HC-SR04`, `valid`, `echo_us`, `state`, and `state_name`.  The state names
  are `waiting_rise` (no ECHO edge seen yet), `waiting_fall` (rising edge seen),
  `timeout`, and `valid`; `waiting_rise` specifically points to the sensor
  VCC/GND/ECHO path or the selected PA12 header rather than ROS parsing.

Keep the robot tracks raised and motion disabled during the first sensor test.
