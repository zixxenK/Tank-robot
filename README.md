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
├── .devcontainer/       # ROS2 Jazzy + ARM toolchain dev environment (Ubuntu 24.04)
├── firmware/
│   ├── stm32_chassis/   # STM32F407 firmware (CMake, ARM GCC)
│   └── esp32_sensors/   # ESP32-S3 camera firmware (PlatformIO)
├── ros2_ws/src/
│   ├── robot_bringup/   # Launch files & hardware configuration
│   ├── robot_teleop/    # PS5 controller + keyboard teleop nodes
│   └── robot_drivers/   # STM32 serial bridge + ESP32 camera bridge
├── deployment/          # systemd auto-start infrastructure
├── scripts/             # Flashing and utility scripts
└── docs/
    ├── system_topology.md           # Full architecture & Endgame structure
    ├── communication_protocols.md   # All communication protocols
    └── flashing_guide.md            # Complete flashing instructions
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

## Flashing

See [docs/flashing_guide.md](docs/flashing_guide.md) for complete flashing instructions.

```bash
# Flash STM32
./scripts/flash_stm32.sh --build

# Flash ESP32
cd firmware/esp32_sensors
pio run -e esp32cam -t upload
```

## Deployment on Rock64

```bash
sudo bash deployment/scripts/rock64_setup.sh --ros-distro auto
```

## Communication Protocols

The project uses three communication protocols:

1. **Rock64 ↔ STM32**: Custom UART protocol with heartbeat and safety watchdog
2. **Rock64 ↔ ESP32**: HTTP MJPEG video stream
3. **STM32 ↔ MPU6050**: I2C sensor protocol

See [docs/communication_protocols.md](docs/communication_protocols.md) for detailed protocol specifications.

## Documentation

- [System Topology](docs/system_topology.md) - Architecture and directory structure
- [Communication Protocols](docs/communication_protocols.md) - All protocol specifications
- [Flashing Guide](docs/flashing_guide.md) - Complete flashing instructions
- [Deployment Guide](deployment/docs/deployment_guide.md) - Rock64 deployment setup

## Supported Platforms

- **Development**: Ubuntu 24.04 (Jazzy) or Ubuntu 22.04 (Humble)
- **Deployment**: Rock64 SBC (Ubuntu 24.04 recommended)
- **STM32**: STM32F407VGTx
- **ESP32**: ESP32-S3-DevKitC-1

## Safety Features

- Motor safety watchdog (200ms command timeout)
- Heartbeat monitoring (500ms timeout)
- Emergency stop on communication failure
- Hardware watchdog on STM32

## License

MIT
