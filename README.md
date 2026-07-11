# Rock64 Ranger — Tank Robot

A differential-drive tracked robot built on the **Hiwonder tank chassis**,
integrating STM32, ESP32-S3, and Rock64 in a clean layered architecture.

## Hardware

| Component | Role |
|-----------|------|
| **STM32F407** | Real-time motor control over UART |
| **ESP32-S3**  | Camera (OV2640), MJPEG HTTP stream over WiFi |
| **Rock64 SBC**| ROS2 runtime, teleoperation, deployment host |
| **Hiwonder Tank Chassis** | Differential-drive tracked platform |

## Repository Structure

```
├── .devcontainer/       # ROS2 Jazzy + ARM toolchain dev environment
├── firmware/
│   ├── stm32_chassis/   # STM32F407 firmware scaffold (CMake)
│   └── esp32_sensors/   # ESP32-S3 camera firmware (PlatformIO)
├── ros2_ws/src/
│   ├── robot_bringup/   # Launch files & hardware configuration
│   ├── robot_teleop/    # PS5 controller + keyboard teleop nodes
│   └── robot_drivers/   # STM32 serial bridge + ESP32 camera bridge
├── deployment/          # systemd auto-start infrastructure
└── docs/
    └── system_topology.md  # Full architecture & Endgame structure
```

## Quick Start (DevContainer)

1. Open in VS Code → **Reopen in Container**
2. The container installs ROS2 Jazzy, ARM GCC, and PlatformIO automatically.

## Building

```bash
# STM32 firmware
cd firmware/stm32_chassis
cmake -B build -DCMAKE_TOOLCHAIN_FILE=cmake/stm32_toolchain.cmake
cmake --build build

# ESP32 firmware
cd firmware/esp32_sensors
pio run -e esp32cam

# ROS2 workspace
cd ros2_ws
colcon build --symlink-install
```

## Deployment on Rock64

```bash
sudo bash deployment/scripts/rock64_setup.sh --ros-distro auto
```

The ROS bringup currently talks to the STM32 over the custom UART bridge in
`robot_drivers`; the optional micro-ROS static library hook in
`firmware/stm32_chassis` is kept disabled until that firmware path exists.

See [deployment/docs/deployment_guide.md](deployment/docs/deployment_guide.md)
and [docs/system_topology.md](docs/system_topology.md) for full details.
