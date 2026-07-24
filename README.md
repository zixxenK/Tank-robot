# Rock64 Ranger - Tank Robot

A differential-drive tracked robot based on the Hiwonder tank chassis, with a split architecture:

- Firmware domain: STM32F407 + ESP32 firmware
- Host domain: Rock64 ROS 2 workspace and launch/deployment stack

## Repository Layout

```text
Tank-robot/
├── firmware/
│   ├── stm32_chassis/        # STM32F407 firmware (CMake, ARM GCC)
│   └── esp32_sensors/        # ESP32-S3 firmware (PlatformIO)
├── host_ws/
│   └── src/                  # Canonical Rock64 ROS 2 workspace (new)
├── ros2_ws/
│   └── src/                  # Backward-compatible workspace (migration source)
├── deployment/
│   ├── scripts/              # Rock64 setup + systemd launch helpers
│   └── systemd/              # Service units and generated config
├── scripts/                  # Firmware build/flash + migration helpers
├── docs/
└── Makefile                  # Unified task runner
```

## Workspace Separation Policy

- Build STM32 firmware only in `firmware/stm32_chassis/build*`.
- Build ROS 2 host packages only in `host_ws/{build,install,log}`.
- Deployment scripts auto-select workspace in this order:
  1. `HOST_WS_PATH` (if set)
  2. `host_ws` (if `host_ws/src` exists)
  3. `ros2_ws` fallback

## Migration to host_ws

Non-destructive copy of packages from `ros2_ws/src` to `host_ws/src`:

```bash
bash scripts/migrate_host_ws.sh
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\migrate_host_ws.ps1
```

Then build from `host_ws`:

```bash
cd host_ws
colcon build --symlink-install
```

## Quick Tasks

```bash
make help
make stm32-build
make host-build
make host-launch
```

## Build and Flash

### STM32 firmware

```bash
cd firmware/stm32_chassis
cmake -S . -B build -DCMAKE_TOOLCHAIN_FILE=cmake/stm32_toolchain.cmake
cmake --build build -j4
```

Windows (no global `cmake` in PATH):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\flash_stm32_windows.ps1 -Build
```

### micro-ROS static library for STM32

```bash
bash scripts/build_microros.sh
```

### Flash STM32

```bash
bash scripts/flash_stm32.sh --build --verify
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\flash_stm32_windows.ps1 -Build -Verify
```

### ESP32 firmware

```bash
cd firmware/esp32_sensors
pio run -e esp32cam
pio run -e esp32cam -t upload
```

## Rock64 Deployment

```bash
sudo bash deployment/scripts/rock64_setup.sh --ros-distro auto
```

This installs dependencies, builds the active host workspace, writes deployment config, and installs/updates the `rock64-robot.service` unit.

## Host Build on Windows

One-command bootstrap for toolchain + PATH setup in current session:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap_windows_dev.ps1
```

To also persist PATH updates to your user profile:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap_windows_dev.ps1 -PersistUserPath
```

If `colcon build` reports `VisualStudioVersion is not set`, use:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_host_windows.ps1
```

This script auto-loads `VsDevCmd.bat` and runs `python -m colcon build --symlink-install` in the selected workspace.

Prerequisite: ROS2 for Windows must be installed (`local_setup.bat` available, e.g. `C:\dev\ros2_humble\local_setup.bat`).
If ROS2 is not installed on Windows, build `host_ws` on Linux/Rock64 instead.

WSL Ubuntu fallback (when ROS2 is installed in WSL):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_host_windows.ps1 -UseWslFallback -WslDistro Ubuntu-22.04 -WslRosDistro humble
```

Direct WSL build helper:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_host_wsl.ps1 -Distro Ubuntu-22.04 -RosDistro humble
```

## Runtime Bringup

```bash
source /opt/ros/humble/setup.bash
cd host_ws
source install/setup.bash
ros2 launch robot_bringup rock64_bringup.launch.py
```

Legacy bridge mode (during migration):

```bash
ros2 launch robot_bringup rock64_bringup.launch.py use_legacy_bridges:=true
```

## Documentation

- `docs/system_topology.md`
- `docs/communication_protocols.md`
- `docs/flashing_guide.md`
- `deployment/docs/deployment_guide.md`

## Platforms

- Development host: Ubuntu 22.04 (ROS 2 Humble)
- Target SBC: Rock64
- MCU: STM32F407VGTx
- Camera module controller: ESP32-S3
