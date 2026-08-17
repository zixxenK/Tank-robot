# Hardware Validation Gate

Do not place the robot on the floor until every raised-track check passes.

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
   exercise each motor independently. Motor 0 is M1/left and motor 1 is
   M2/right.
7. Record expected direction, PWM channel, encoder timer, encoder sign, and
   ticks per output-shaft revolution for motors 0 through 3.
8. Confirm Motor 2 uses TIM2 without its `ARR` or prescaler changing.
9. Confirm Motor 4 reports TIM3 encoder movement.
10. Stop host commands and verify the 250 ms firmware command timeout zeros
    PWM directly.
11. Disconnect the Rock64 link and verify the firmware timeout zeros PWM.

## Rock64 Integration

1. Verify `/dev/rock64_stm32` resolves to the Hiwonder WCH USB-UART
   `/dev/ttyACM*` device, with USB identity `1a86:55d4`, and configure it for
   USART1 on PA9/PA10 at 1,000,000 8N1. The product connector is labeled
   UART1. ST-Link `0483:3748` is
   flash/debug only.
   The safe proof command sends only stop/zero frames and fails on a zero-byte
   or invalid response: `python3 scripts/motor_link_safe_test.py`.
2. Launch with no transport overrides.
3. Confirm the active graph contains `safety_gateway`, `ps5_ros_bridge`, and
   `stm32_hardened_bridge` and no raw-command hardware subscriber.
4. Publish fresh battery telemetry and a low-speed `/cmd_vel`; confirm output
   on `/ranger/cmd_vel_safe` is clamped by the installed safety parameters.
5. Trigger and clear operator e-stop; confirm motion resumes only after a new
   command.
6. Trigger critical battery; confirm operator e-stop clear does not clear the
   battery latch.
7. Hold voltage above recovery for the configured interval and call
   `/safety/reset_battery_latch`; confirm reset succeeds.
8. Restart the bridge while a nonzero source command exists. Confirm reconnect
   sends emergency stop and requires a fresh safe command before motion.
9. Verify encoder, battery, IMU, odometry, and diagnostic topics for freshness
   and plausible units.

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
