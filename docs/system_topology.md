# System Topology

The production transport assignment is defined by
[`SOURCE_OF_TRUTH_1_0.md`](SOURCE_OF_TRUTH_1_0.md).

## Runtime Graph

```text
PS5 DualSense (optional)                  Autonomous agent
      |                                         |
  /cmd_vel                         /agent/cmd_vel_proposed
      |                                  + /agent/heartbeat
      +-------------------+---------------------+
                          v
                    safety_gateway
             e-stop | battery | limits | timeout
                          |
                /ranger/cmd_vel_safe
                          |
                stm32_hardened_bridge
          reconnect | serial timeout
                          |
             UART1 -> USART1 -> PA9/PA10 (WCH packed binary)
                          |
                       STM32F407
       command timeout | PID | PWM | encoders
```

The only host node allowed to emit motor frames is
`stm32_hardened_bridge`. Direct motor topics and raw `/cmd_vel` hardware
subscriptions are not part of the product graph.

The bridge also owns the guarded commissioning services
`/stm32/motor_1/enable` and `/stm32/motor_2/enable` (`std_srvs/SetBool`). A
`true` request runs only that motor at the configured proof speed while holding
the other at zero; `false` stops it. These services are for raised-track
testing and never create a second serial writer.

For the operator-directed base test, publish one command to
`/stm32/test_direction` (`std_msgs/String`): `forward`, `back`, or `stop`.
The STM32 bridge remains the only serial writer and continuously refreshes the
250 ms firmware command watchdog until `stop` is received.

## Ownership

| Component | Responsibility |
| --- | --- |
| `robot_teleop` | Produce PS5 DualSense velocity proposals on `/cmd_vel` |
| `navigation` / `terrain_adaptation` | Produce future proposal topics only; no direct operator or hardware authority |
| `agent_core/safety_gateway` | Select source and enforce host safety policy |
| `stm32_hardened_bridge` | Encode safe commands and manage the serial link |
| STM32 packed protocol | Validate frames and enforce communication timeouts |
| STM32 motor control | Encoder feedback, PID, PWM, immediate hard stop |
| ESP32 camera bridge | Optional MJPEG-to-ROS image path; no motor authority |

## Repository

```text
firmware/
  stm32_chassis/        Active STM32 firmware
  esp32_sensors/        Camera firmware
host_ws/src/
  agent_core/           Safety policy
  robot_bringup/        Canonical launch and parameters
  robot_drivers/        Hardened STM32 and camera bridges
  robot_teleop/         PS5 DualSense input

deployment/             Rock64 setup and systemd service
scripts/                Reproducible developer commands
stubs/                  Windows-only ROS typing/test shims
docs/                   Current architecture and validation references
```

`host_ws` is the only ROS workspace. Build products remain under each domain:

- STM32: `firmware/stm32_chassis/build/<preset>`
- ROS 2: `host_ws/build`, `host_ws/install`, `host_ws/log`
- ESP32: `firmware/esp32_sensors/.pio`

These directories are generated and ignored by Git.

## Safety State

The safety gateway publishes at 50 Hz. Stop reasons override all command
sources:

1. Operator e-stop
2. Critical-battery latch or unavailable/stale battery telemetry
3. Agent heartbeat loss for autonomous commands
4. Source command timeout

Fresh teleop has priority over autonomous commands. Clearing operator e-stop
does not clear a battery latch. Battery reset requires fresh telemetry above
the recovery threshold for the configured stability interval.

## Deferred Hardware Facts

The following remain physical validation items rather than software claims:

- Motor direction and side polarity
- Encoder counts per revolution and sign
- Battery divider calibration
- IMU orientation and units
- Rock64 USB-UART identity and boot-time availability
