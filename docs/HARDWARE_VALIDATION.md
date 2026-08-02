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
4. Confirm boot diagnostics and whether the previous reset was IWDG-caused.
5. Send heartbeat and zero-speed packed frames before enabling motor power.
6. Exercise each motor independently at the lowest effective command.
7. Record expected direction, PWM channel, encoder timer, encoder sign, and
   ticks per output-shaft revolution for motors 0 through 3.
8. Confirm Motor 2 uses TIM2 without its `ARR` or prescaler changing.
9. Confirm Motor 4 reports TIM3 encoder movement.
10. Stop host commands and verify the 200 ms firmware command timeout zeros
    PWM directly.
11. Stop heartbeats and verify the 500 ms heartbeat timeout zeros PWM.
12. Inject a control-task stall longer than the configured IWDG interval;
    confirm MCU reset and zero PWM during reset.

## Rock64 Integration

1. Verify `/dev/rock64_stm32` resolves to the intended USB-UART device.
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
   sends emergency stop and requires firmware heartbeat plus a fresh safe
   command before motion.
9. Verify encoder, battery, IMU, odometry, and diagnostic topics for freshness
   and plausible units.

## Controlled Floor Test

1. Set conservative speed and acceleration limits.
2. Attach a physical or immediately accessible power cutoff.
3. Test forward, reverse, and in-place rotation at low speed.
4. Verify stop distance for command timeout, e-stop, host process termination,
   serial disconnect, and STM32 reset.
5. Run a stationary telemetry soak, then a low-speed motion soak.

Record every measured parameter in the canonical configuration before raising
limits. A failed item blocks deployment; restore the previous known firmware
image and configuration rather than bypassing a safety layer.
