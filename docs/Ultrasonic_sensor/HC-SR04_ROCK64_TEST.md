# HC-SR04 test checklist

> The authoritative wiring and end-to-end build path is
> [`../ULTRASONIC_BUILD_PATH.md`](../ULTRASONIC_BUILD_PATH.md). This file is
> only the short bench checklist.

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

The image drives J4/PC8 as TRIG and listens for rising/falling edges on J2/PA12
as ECHO. Split the HC-SR04 four-wire lead across those two three-pin headers;
use the signal contact on each. Use a divider or level shifter on the 5 V ECHO
line unless the complete input path on this exact controller is verified safe.

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
  VCC/GND/ECHO path or the selected connector pair rather than ROS parsing.

Keep the robot tracks raised and motion disabled during the first sensor test.
