# Tank-Robot Execution Directive

This is the codebase-specific version of the operator directive.

## Non-Negotiable Rules

1. The PC never flashes the STM32 directly.
2. Firmware release work always updates the Rock64 first, then builds, flashes,
   verifies, starts the image, and runs the safe UART proof on the Rock64.
3. The production STM32 motor-data path is `/dev/rock64_stm32` through the WCH
   USB-UART adapter to STM32 USART1 PA9/PA10.
4. Rock64 Pi-2 header UART/I2C/SPI pins are for direct Rock64 sensors, not the
   production STM32 motor link.
5. Operator commands must be one-shot and summarized. Logs go to `log/e2e/`;
   the terminal shows a Mission Report.

## One-Shot Commands

| Operator intent | Command | Behavior |
|---|---|---|
| Local/offline E2E | `.\run_e2e.ps1` or `./run_e2e.sh` | Runs environment gate, offline contracts, available builds, safe hardware checks when present, and cleanup |
| PC to Rock64 source update | `.\scripts\sync_rock64_safe.ps1 -RestartService` | Syncs source/configuration, rebuilds ROS on the Rock64, restarts service, does not flash |
| Firmware release | `.\scripts\deploy_rock64.ps1` | Syncs to Rock64, then Rock64 builds, flashes, verifies, starts STM32 app, and runs safe UART proof |
| Rock64 local release | `bash deployment/scripts/rock64_update_and_flash.sh` | Same release workflow, already running on the robot host |

## Hardware Control Boundary

The Rock64 hosts ROS 2, safety policy, teleop/autonomy, and the hardened STM32
bridge. The STM32 owns motor PWM/current behavior, encoder sampling, watchdog,
and packed binary telemetry. Track kinematics stay in ROS as differential
skid-steer setpoints; raw motor electrical limits stay in firmware. The host
bridge uses the full signed motor-command range by default and records the
1.5A stall-current boundary as a runtime parameter. The STM32 remains
authoritative for PID, watchdog, e-stop, and electrical protection.
