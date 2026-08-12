# System Topology

## Runtime Graph

```text
PS5 / keyboard                           Autonomous agent
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
          heartbeat | reconnect | serial timeout
                          |
                USART1 packed binary
                          |
                       STM32F407
       command timeout | IWDG | PID | PWM | encoders
```

The only host node allowed to emit motor frames is
`stm32_hardened_bridge`. Direct motor topics and raw `/cmd_vel` hardware
subscriptions are not part of the product graph.

## Ownership

| Component | Responsibility |
| --- | --- |
| `robot_teleop` | Produce operator velocity proposals |
| `agent_core/safety_gateway` | Select source and enforce host safety policy |
| `stm32_hardened_bridge` | Encode safe commands and manage the serial link |
| STM32 packed protocol | Validate frames and enforce communication timeouts |
| STM32 motor control | Encoder feedback, PID, PWM, immediate hard stop |
| STM32 IWDG | Reset the MCU if the control iteration stalls |
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
  robot_teleop/         PS5 and keyboard input

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
- IWDG measured timeout under LSI tolerance
- Rock64 USB-UART identity and boot-time availability
