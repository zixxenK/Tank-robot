# End-to-end integration reference

This document describes the current graph and the safe extension boundary.
The operator procedure is [OPERATOR_GUIDE.md](OPERATOR_GUIDE.md); this file is
the technical wiring reference for future lab-assistant work.

## Active milestone

```text
PS5 DualSense -> /cmd_vel --------------------+
                                               v
ESP32 camera -> /camera/image_raw       safety_gateway
USB camera   -> /camera/usb/image_raw          |
STM32 IMU    -> /stm32/imu                     v
STM32 odom   -> /stm32/odom             /ranger/cmd_vel_safe
                                               |
                                      stm32_hardened_bridge
                                               |
                                  WCH UART1 -> STM32 USART1
```

The active acceptance gate covers the STM32 bridge, left/right encoder
telemetry, derived odometry, the project's QMI8658 runtime path, PS5 input,
and both cameras. The board's published IMU identity is contradictory; the
runtime diagnostic is the acceptance authority.
Servo, battery, HC-SR04 ultrasonic, and LiDAR checks are optional until their
hardware is commissioned.

## Future proposal path

Perception, navigation, terrain adaptation, and LM Studio are future-facing
lab-assistant components. They must remain outside the operator lane:

```text
goal/map/camera/IMU
       |
       v
navigation -> /agent/cmd_vel_planned
       |
terrain_adaptation -> /agent/cmd_vel_proposed
       |
LM Studio / agent supervisor -> /agent/heartbeat
       +---------------------->
                         safety_gateway
```

The safety gateway accepts `/agent/cmd_vel_proposed` only while the agent
heartbeat is fresh. Therefore launching a planner or terrain node alone cannot
authorize motion. No autonomous node publishes to `/cmd_vel`, and no future
node may write to the STM32 serial link directly.

## Topic ownership

| Topic | Owner or source | Role |
| --- | --- | --- |
| `/cmd_vel` | PS5/keyboard and raised-track maintenance tools | Operator proposal lane |
| `/agent/cmd_vel_planned` | Navigation | Internal autonomous proposal |
| `/agent/cmd_vel_proposed` | Agent/terrain proposal boundary | Heartbeat-gated proposal |
| `/agent/heartbeat` | Authorized agent supervisor | Autonomous motion authority |
| `/ranger/cmd_vel_safe` | Safety gateway | Final host-safe command |
| `/stm32/odom` | Hardened STM32 bridge | Canonical hardware odometry |
| `/stm32/imu` | Hardened STM32 bridge | Onboard QMI8658 telemetry |
| `/camera/image_raw` | ESP32 camera bridge | Primary camera image |
| `/camera/usb/image_raw` | USB camera bridge | Secondary camera image |

## Launch profiles

Use `rock64_bringup.launch.py` for the active hardware acquisition and PS5
profile. `full_stack.launch.py` includes that graph but defaults perception,
navigation, and terrain adaptation off; those options are explicitly future
profiles and remain heartbeat-gated when enabled.

Use `pc_dashboard.launch.py` for read-only Foxglove, TF completion, and
optional SLAM on the PC/WSL side. The old `rock64_dashboard.launch.py` name is
only a compatibility alias for that PC-only launch.

Use `gazebo_telemetry.launch.py` only for simulation. Simulation remaps Gazebo
topics to `/cmd_vel` and `/odom` inside the simulation profile; it does not
change the production hardware topics or the production safety boundary.

## LM Studio boundary

LM Studio runs on the PC/WSL side with its token supplied through
`LM_API_TOKEN`. Its codegen and diagnostics nodes are read-only. Its bounded
teleop node publishes only to the agent proposal and heartbeat topics, with
short finite commands. See [LM_STUDIO_INTEGRATION.md](LM_STUDIO_INTEGRATION.md)
and [ROADMAP.md](ROADMAP.md) before adding tools or autonomous arbitration.
