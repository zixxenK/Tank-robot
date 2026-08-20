# STL-50B2 direct ROCK64 integration

The STL-50B2 is connected directly to the ROCK64 UART2 alternate function. It
does not use the STM32 UART and it does not use `ydlidar_ros2_driver`,
`delta_lidar_ros2`, or `hls_lfcd_lds_driver`.

| LiDAR wire | Function | ROCK64 header | Signal |
| --- | --- | --- | --- |
| Blue | +5 V | 2 | 5 V power |
| Green | GND | 6 | Ground |
| Yellow | LiDAR TX | 10 | GPIO2_A1 / UART2_RX_M1 |
| Black | LiDAR RX | 8 | GPIO2_A0 / UART2_TX_M1 |
| Red | Hardware sync | 12 | GPIO2_A3 |

The UART is `115200 8N1`, with no flow control. The default Linux device is
`/dev/ttyS2`, but the actual device must be confirmed on the running ROCK64
because kernel aliases can differ. UART2 must be enabled and the pins must be
muxed to UART2 by the board device tree. Do not assume that physical wiring
alone enables the UART.

Pin 12 is required. The driver uses its rising edge as the scan boundary and
does not publish packets received before the first sync edge. The default GPIO
mapping is `/dev/gpiochip2`, line offset `3` (`GPIO2_A3`), with a legacy sysfs
fallback for older ROCK64 kernels. The user running ROS must have access to the
serial device and GPIO character device (normally `dialout` and `gpio` groups,
depending on the image).

## Driver and parser

The package contains `robot_drivers/stl50b2_parser.py`, a dependency-free
stream parser for the LDROBOT STL packet format:

- header `0x54 0x2c`;
- 47-byte packet;
- little-endian speed, start/end angles, timestamp;
- 12 distance/intensity samples;
- LDROBOT CRC-8 over bytes 0 through 45.

`stl50b2_lidar` publishes synchronized `sensor_msgs/LaserScan` messages on
`/scan` with frame `base_laser`.

## Build and run

```bash
cd ~/Tank-robot/host_ws
colcon build --symlink-install --packages-select robot_drivers robot_bringup
source install/setup.bash
ros2 launch robot_bringup stl50b2.launch.py
```

Verify the port and GPIO before launching:

```bash
ls -l /dev/ttyS2 /dev/gpiochip2
gpioinfo /dev/gpiochip2
ros2 topic echo /scan --qos-reliability best_effort
```

If the UART is exposed under another device name, pass it explicitly:

```bash
ros2 launch robot_bringup stl50b2.launch.py serial_port:=/dev/ttyS3
```

The existing `rock64_bringup.launch.py` intentionally does not start this
node by default, so a missing LiDAR cannot prevent motor bringup. Start the
dedicated launch above once the UART and sync line have been validated.
