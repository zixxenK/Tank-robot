# Tank Robot lab-assistant roadmap

This table records what is active now and what can be added without changing
the drive safety boundary.

| Subsystem | Status | Upgrade direction |
| --- | --- | --- |
| PS5 tracked drive and drift | Active | Tune alpha/beta from measured track grip and current/temperature logs. |
| STM32 onboard QMI8658 | Active gate | Add calibrated orientation covariance and IMU-based slip/turn diagnostics. |
| ESP32 and USB cameras | Active gate | Add timestamp/health monitoring, stereo or paired-camera calibration, and perception consumers. |
| LM Studio assistant | In progress | Keep PC/WSL-hosted, review-only codegen, bounded commands, explicit tools, and safety-gateway mediation. |
| Diagnostics aggregation | In progress | Add a shared health model and historical fault events for the lab assistant. |
| Navigation and waypoint planning | Future | Commission maps, TF, odometry, and autonomous command arbitration before enabling. |
| Perception | Future | Build read-only camera inference first; feed only reviewed, bounded proposals to the agent layer. |
| Terrain adaptation | Future | Use validated IMU/encoder evidence to tune speed and pivot behavior; never bypass safety limits. |
| LiDAR | Optional | Enable after serial/GPIO wiring and `/scan` acceptance are proven. |
| Hiwonder Glowy ultrasonic | Optional | Keep as a future proximity input on shared I2C2; it is not in the active drive gate. |
| Servo and accessory outputs | Optional | Re-enable acceptance only when a lab task needs the actuator. |
| Battery telemetry | Optional | Calibrate the ADC divider and make it required before battery-aware autonomy. |

## Guardrails for future upgrades

Future lab-assistant capabilities must consume ROS telemetry and publish
proposals through reviewed interfaces. No LM Studio, perception, navigation,
or terrain node may write to the STM32 serial link or command motors directly.
Every new actuator path must retain finite checks, bounded duration, command
freshness, e-stop behavior, and a hardware acceptance test.
