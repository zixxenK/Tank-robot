# Hardware Validation Gate (technical appendix)

The current operator workflow is [OPERATOR_GUIDE.md](OPERATOR_GUIDE.md).
This appendix contains the deeper evidence and fault-injection checks. The
active milestone is drive, camera, and the project's QMI8658 runtime path;
Hiwonder's live product/hardware pages still label the IMU MPU6050, so the
acceptance gate requires WHO_AM_I evidence. Servo, battery,
HC-SR04 ultrasonic, and LiDAR checks remain optional future-upgrade gates.

Do not place the robot on the floor until every raised-track check passes.
The production wiring and transport assignments are defined by
[`SOURCE_OF_TRUTH_1_0.md`](SOURCE_OF_TRUTH_1_0.md).

## Build Evidence

Record before flashing:

- Git commit and dirty status
- Debug and Release firmware SHA-256 hashes
- ELF, BIN, and HEX sizes
- `arm-none-eabi-size` output
- Host `colcon test-result --verbose`
- Safety and protocol unit-test results

## STM32 Bench

1. Disconnect motor power while flashing.
2. Clear the work area and raise all tracks.
3. Flash the Release image and verify read-back.
4. Confirm boot diagnostics and that PWM outputs are zero after boot.
5. Send the emergency-stop and zero-speed packed frames before enabling motor
   power. Heartbeat frames are not required by the canonical USART1 runtime.
6. With tracks lifted, call `/stm32/motor_1/enable` and
   `/stm32/motor_2/enable` as `std_srvs/SetBool` (`true`, then `false`) to
   exercise each motor independently. Motor 0 is M1/left on TIM2 and motor 1
   is M2/right on TIM5; the active PWM routes are M1 PE9/PE11 and M2
   PE13/PE14.
7. Record expected direction, PWM channel, encoder timer, encoder sign, and
   ticks per output-shaft revolution for motors 0 through 3.
8. Confirm Motor 1 uses TIM2 without its `ARR` or prescaler changing.
9. Confirm the active left/right encoder pair reports movement. The spare
   encoder channels are not part of the current two-track acceptance gate.
10. Stop host commands and verify the 250 ms firmware command timeout zeros
    PWM directly.
11. Disconnect the Rock64 link and verify the firmware timeout zeros PWM.

## Rock64 Integration

1. Follow [`SOURCE_OF_TRUTH_1_0.md`](SOURCE_OF_TRUTH_1_0.md) for the transport
   assignment. Verify `/dev/rock64_stm32` resolves to the Hiwonder WCH USB-UART
   `/dev/ttyACM*` device, with USB identity `1a86:55d4`, and configure it for
   USART1 on PA9/PA10 at 1,000,000 8N1. The product connector is labeled
   UART1. ST-Link `0483:3748` is
   flash/debug only.
   The safe proof command sends only stop/zero frames and fails on a zero-byte
   or invalid response: `python3 scripts/motor_link_safe_test.py`.
2. Launch with no transport overrides.
3. Confirm the active graph contains `safety_gateway`, `ps5_ros_bridge`, and
   `stm32_hardened_bridge` and no raw-command hardware subscriber.
4. Publish a low-speed `/cmd_vel`; confirm output on
   `/ranger/cmd_vel_safe` is finite and bounded by the installed safety
   parameters. Battery gating is a separate optional check until ADC
   calibration is complete.
5. Trigger and clear operator e-stop; confirm motion resumes only after a new
   command.
6. Trigger critical battery; confirm operator e-stop clear does not clear the
   battery latch.
7. Hold voltage above recovery for the configured interval and call
   `/safety/reset_battery_latch`; confirm reset succeeds.
8. Restart the bridge while a nonzero source command exists. Confirm reconnect
   sends emergency stop and requires a fresh safe command before motion.
9. Verify encoder, IMU, odometry, camera, and diagnostic topics for freshness
   and plausible units. Verify battery only when `MONITOR_BATTERY=true` is
   intentionally enabled.

## Controlled Floor Test

1. Set conservative speed and acceleration limits.
2. Attach a physical or immediately accessible power cutoff.
3. Test forward, reverse, and in-place rotation at low speed.
4. Verify stop distance for command timeout, e-stop, host process termination,
   serial disconnect, and STM32 reset.
5. Run a stationary telemetry soak, then a low-speed motion soak.

Recommended bench command for the tread pair:

```bash
make host-motor-test
```

This starts the hardened bridge, keeps teleop disabled, and publishes the
existing low-speed one-track-at-a-time sequence that validates M1/M2 direction
before the floor test. The direct proof script
`scripts/motor_start_stop_test.py --confirm` is also available before ROS 2.

Record every measured parameter in the canonical configuration before raising
limits. A failed item blocks deployment; restore the previous known firmware
image and configuration rather than bypassing a safety layer.
