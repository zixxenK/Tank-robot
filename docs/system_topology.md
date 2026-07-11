# docs/system_topology.md
# Rock64 Ranger — System Topology & Endgame Directory Structure

## Overview

This document defines the **Endgame** (Clean Slate) directory structure for
the Rock64 Ranger project. All migration work should converge to this layout.

## Hardware Stack

| Component | Role |
|-----------|------|
| **STM32F407** | Real-time motor control, encoder feedback, UART motor endpoint |
| **ESP32-S3**  | Camera (OV2640/OV5640), MJPEG HTTP server, WiFi bridge |
| **Rock64**    | Linux SBC, ROS2 runtime, high-level control, deployment host |
| **Hiwonder Tank Chassis** | Differential-drive tracked platform |

## Communication Architecture

```
[PS5 Controller] ──USB──► Rock64 (ROS2)
                            │
                    /cmd_vel│ (geometry_msgs/Twist)
                            │
                     [robot_drivers]
                       │         │
            Custom UART serial   HTTP MJPEG
                       │         │
                  [STM32F407]  [ESP32-S3]
                  Motor L/R    Camera stream
                                    │
                        /camera/image_raw
```

## Endgame Directory Structure (Target)

```
/rock64-robot-project                    ← repo root
├── .devcontainer/
│   ├── devcontainer.json                ← ROS2 Jazzy + STM32 dev environment
│   └── install-toolchain.sh             ← ARM GCC + system deps installer
│
├── firmware/                            # Bare-metal / Embedded code
│   ├── stm32_chassis/                   # STM32F407 firmware scaffold
│   │   ├── Core/
│   │   │   ├── Inc/                     # HAL + motor driver headers
│   │   │   ├── Src/                     # HAL + motor driver sources
│   │   │   └── STM32F407VGTx_FLASH.ld  # Linker script
│   │   ├── micro_ros_lib/
│   │   │   └── libmicroros.a            # Optional micro-ROS static lib (gitignored)
│   │   ├── cmake/
│   │   │   └── stm32_toolchain.cmake    # ARM cross-compilation toolchain
│   │   └── CMakeLists.txt               # Build system entry point
│   │
│   └── esp32_sensors/                   # Vision / Sensor firmware (ESP32-S3)
│       ├── src/
│       │   └── main.cpp                 # Camera init + MJPEG HTTP server
│       └── platformio.ini               # PlatformIO build config
│
├── ros2_ws/                             # ROS2 Application Workspace
│   └── src/
│       ├── robot_bringup/               # Launch files, URDFs, param YAMLs
│       │   ├── launch/
│       │   │   └── rock64_bringup.launch.py
│       │   ├── package.xml
│       │   └── CMakeLists.txt
│       │
│       ├── robot_teleop/                # PS5 + keyboard teleop nodes (NEW)
│       │   ├── robot_teleop/
│       │   │   ├── ps5_ros_bridge.py
│       │   │   └── keyboard_teleop.py
│       │   ├── setup.py
│       │   └── package.xml
│       │
│       └── robot_drivers/               # Hardware bridge nodes (NEW)
│           ├── robot_drivers/
│           │   ├── stm32_serial_bridge.py
│           │   └── esp32_camera_bridge.py
│           ├── setup.py
│           └── package.xml
│
├── deployment/                          # Infrastructure as Code
│   ├── systemd/
│   │   ├── rock64-robot.service         # systemd unit (auto-start)
│   │   └── systemd_config.conf.example  # config template
│   ├── scripts/
│   │   ├── rock64_setup.sh              # full setup script
│   │   ├── apply_systemd.sh             # service install/restart
│   │   ├── robot_start.sh               # ROS2 launch orchestrator
│   │   └── source_ros2_ws.sh            # ROS2 env sourcing
│   └── docs/
│       └── deployment_guide.md
│
├── docs/
│   └── system_topology.md               ← this file
│
├── .gitignore                           # No build artifacts at repo root
└── README.md
```

## Build Artifact Policy (No Build Root Rule)

Build outputs must **never** appear at the repository root:

| Layer | Allowed build location | Blocked at root |
|-------|----------------------|-----------------|
| ROS2 workspace | `ros2_ws/build/`, `ros2_ws/install/`, `ros2_ws/log/` | `build/`, `install/`, `log/` |
| STM32 CMake | `firmware/stm32_chassis/build/` | `build/` |
| PlatformIO | `firmware/esp32_sensors/.pio/` | `.pio/` |
| Python | `ros2_ws/src/<pkg>/.venv/` | `.venv/` |

## Key Entry Points

| # | Entry Point | File | Description |
|---|-------------|------|-------------|
| 1b | STM32 optional micro-ROS hook | `firmware/stm32_chassis/CMakeLists.txt` | Optional static lib path |
| 2b | ESP32 camera lib dep | `firmware/esp32_sensors/platformio.ini:17` | `esp32-camera` |
| 3c | ROS2 bringup launch | `ros2_ws/src/robot_bringup/launch/rock64_bringup.launch.py` | Hardware nodes |
| 4c | ROS distro detection | `deployment/scripts/rock64_setup.sh:70` | Ubuntu→ROS2 map |
| 6a | Endgame root | This file — `/rock64-robot-project` | Target structure |

## Current STM32 Transport Decision

The checked-in ROS 2 stack currently uses the Python UART bridge in
`robot_drivers/stm32_serial_bridge.py` to send motor commands from `/cmd_vel`
to the STM32. The `firmware/stm32_chassis/micro_ros_lib/` directory and CMake
hook are retained only as an optional future integration point; they are not
part of the default bringup path today.
