# Rock64 one-command hardware bring-up and test

Run these commands on the Ubuntu Rock64 from the repository root.

## One-time firmware and ROS deployment

This release adds the STM32 servo protocol, so the STM32 must be rebuilt and
flashed once before the servo test can pass:

```bash
bash deployment/scripts/rock64_update_and_flash.sh
```

The deployment keeps HC-SR04 on J4/PC8 (TRIG) and J2/PA12 (ECHO), and enables
only the SG90 connected to J1/PA11. It also enables the STM32 bridge, PS5
bridge, ESP32 camera bridge, USB camera bridge, and compressed camera transport
in the Rock64 service config.

## Start everything

```bash
bash scripts/onecmd.sh
```

That is the persistent all-hardware start command. When the systemd service is
installed, the script restarts that single service instead of opening a second
copy of the STM32 serial port. Run it again whenever the hardware stack needs a
clean restart.

## Test everything in order

First run all tests that do not move the tracks:

```bash
bash scripts/hardware_acceptance.sh
```

For the complete test, physically raise and secure both tracks, keep the power
cutoff within reach, place a solid target 2 cm to 4 m in front of the HC-SR04,
then run one command:

```bash
bash scripts/hardware_acceptance.sh --tracks-raised
```

Add `--with-lidar` only when the STL-50B2 is connected and must also pass:

```bash
bash scripts/hardware_acceptance.sh --tracks-raised --with-lidar
```

The runner performs and prints these stages one at a time:

1. STM32 UART: requires multiple fresh, CRC-valid firmware frames.
2. Encoders: requires fresh left and right count messages.
3. Odometry: requires fresh finite pose/twist messages with a unit quaternion;
   this proves the derived navigation input, not only the raw encoder topic.
4. IMU: requires finite, physically plausible acceleration and gyro samples.
5. HC-SR04: requires multiple fresh, finite echoes in its valid range.
6. Battery voltage: reported as `SKIP` by default because this firmware image
   has one uncalibrated ADC channel. Set `MONITOR_BATTERY=true` (or
   `require_battery:=true`) after the divider and pack are calibrated to make
   finite 9.0–13.0 V telemetry a required stage.
7. PS5: requires `connected=1`, then prompts for one real stick/button input
   while the ROS emergency stop holds the motors.
8. ESP32 camera: requires advancing, valid `/camera/image_raw` frames.
9. USB camera: requires advancing, valid `/camera/usb/image_raw` frames.
10. STL-50B2: skipped unless `--with-lidar` is supplied.
11. SG90: commands center/low/high/center and requires a fresh STM32
   acknowledgement after every position. Watch the servo make the sweep; an
   SG90 has no position-feedback wire, so ROS can prove the command and PWM
   path but cannot electrically measure the horn angle.
12. M1/left track: at the fixed 0.10 commissioning speed, requires left
   encoder movement and little right-encoder movement.
13. M2/right track: performs the corresponding independent proof.

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
