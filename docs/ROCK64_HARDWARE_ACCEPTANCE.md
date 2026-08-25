# Rock64 one-command hardware bring-up and test

Run these commands on the Ubuntu Rock64 from the repository root.

## One-time firmware and ROS deployment

The current release owns the drive, camera, and project QMI8658 runtime-path acceptance
path. Servo, Glowy ultrasonic, LiDAR, and battery are accessory/future-upgrade
hardware and are outside this basic acceptance workflow.

```bash
bash deployment/scripts/rock64_update_and_flash.sh
```

The deployment enables the STM32 bridge, PS5 bridge, ESP32 camera bridge, USB
camera bridge, and compressed camera transport in the Rock64 service config.
The accessory drivers remain disabled in the basic profile.

## Start everything

```bash
bash scripts/onecmd.sh
```

That is the persistent all-hardware start command. When the systemd service is
installed, the script restarts that single service instead of opening a second
copy of the STM32 serial port. Run it again whenever the hardware stack needs
a clean restart.

## Test everything in order

First run the basic checks without moving the tracks:

```bash
bash scripts/hardware_acceptance.sh
```

For the complete drive test, physically raise and secure both tracks and keep
the power cutoff within reach, then run one command:

```bash
bash scripts/hardware_acceptance.sh --tracks-raised
```

The runner performs and prints these basic stages one at a time:

1. STM32 UART: requires multiple fresh, CRC-valid firmware frames.
2. Encoders: requires fresh left and right count messages.
3. Odometry: requires fresh finite pose/twist messages with a unit quaternion;
   this proves the derived navigation input, not only the raw encoder topic.
4. Onboard IMU: requires finite, physically plausible acceleration and gyro
   samples plus a ready diagnostic from the project QMI8658 path on I2C2
   PB10/PB11. The live Hiwonder product/hardware pages label the part MPU6050,
   so the runner also requires the QMI WHO_AM_I proof.
5. PS5: reported as informational `SKIP`; the service still launches the
   teleoperation node, but no controller activity is required for acceptance.
6. ESP32 camera: requires advancing, valid `/camera/image_raw` frames.
7. USB camera: requires advancing, valid `/camera/usb/image_raw` frames.
8. M1/left track: at the fixed 0.10 commissioning speed, requires left
   encoder movement and little right-encoder movement.
9. M2/right track: performs the corresponding independent proof.

The basic runner does not launch or report the SG90, Glowy ultrasonic,
STL-50B2 LiDAR, or battery checks.

Every exit path requests both motor stops and latches `/safety/e_stop=true`.
After inspecting the result, press the PS5 **Options** button to clear that
latch for normal driving. The complete machine-readable result is written to:

```text
/tmp/tank_robot_hardware_test_report.json
```

`OVERALL PASS` means every required stage passed. A motor stage is reported as
`SKIP`, not `PASS`, unless `--tracks-raised` was explicitly supplied.

## ESP32 connection boundary

The ESP32 USB cable supplies power and programming/serial access. Camera data
reaches the Rock64 over Wi-Fi as MJPEG and is converted to ROS 2 by
`esp32_camera_bridge`. Therefore the ESP32 stage requires the credentials in
its flashed firmware and `CAMERA_IP_STATION` in
`deployment/systemd/systemd_config.conf` to identify the same reachable device.
