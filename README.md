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
make onecmd
make host-unify
```

`make onecmd` is the shortest path for a prepared Rock64 host: it sources the
active ROS 2 workspace and launches the Gazebo telemetry stack in one step.

One-shot host unify + launch (Ubuntu 22.04 + ROS2 Humble):

```bash
make host-unify
```

This target installs missing Gazebo/RViz dependencies, rebuilds host packages,
verifies launch install layout, and launches:

```bash
ros2 launch robot_bringup gazebo_telemetry.launch.py
```

Hardware-only one shot (no apt install step):

```bash
make host-unify-hw
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

Default launch profile uses legacy STM32/ESP32 bridges. This matches the
active firmware integration path and avoids micro-ROS/legacy serial conflicts.

Enable explicit micro-ROS mode when firmware is built for that control path:

```bash
ros2 launch robot_bringup rock64_bringup.launch.py \
  use_micro_ros:=true \
  use_legacy_bridges:=false
```

Optional legacy-binary mode:

```bash
ros2 launch robot_bringup rock64_bringup.launch.py \
  use_legacy_bridges:=true \
  use_binary_bridge:=true
```

### Bringup preflight gate

`rock64_bringup.launch.py` now runs launch-time preflight validation and aborts
before node startup when mode/serial selections are inconsistent. It blocks on:

- both `use_micro_ros` and `use_legacy_bridges` set `false`
- both set `true` while `allow_mixed_bridges:=false`
- missing serial device for selected transport mode
- mixed mode sharing the same serial device for micro-ROS and legacy bridges

### Bridge diagnostics and encoder telemetry

- `/stm32/bridge_alive` (`std_msgs/Bool`) for fast liveness checks
- `/stm32/diagnostics` (`diagnostic_msgs/DiagnosticArray`) unified bridge +
  encoder freshness diagnostics
- `/stm32/encoder_ticks` (`std_msgs/Int32MultiArray`) raw encoder ticks when
  STM32 sends `ENC` telemetry lines (for example `ENC:123,456`)

## Gazebo Harmonic scaffold (ros_gz)

Install sim dependencies (Ubuntu 22.04 / Humble target):

```bash
sudo apt-get update
sudo apt-get install -y ros-humble-ros-gz
```

Launch the minimal tank world with ROS/Gazebo bridge:

```bash
source /opt/ros/humble/setup.bash
cd host_ws
source install/setup.bash
ros2 launch robot_bringup gazebo_harmonic.launch.py
```

Launch Gazebo + RViz telemetry overlays (`/odom`, `/cmd_vel`, encoder ticks):

```bash
ros2 launch robot_bringup gazebo_telemetry.launch.py
```

SSH-friendly one-command launch for a ready Rock64 host:

```bash
bash scripts/onecmd.sh
```

Bridged topics in the scaffold:

- `/clock`
- `/cmd_vel` (ROS -> Gazebo)
- `/odom` (Gazebo -> ROS)

## STM32 encoder output alignment

See `docs/stm32_encoder_telemetry_guide.md` for exact STM32 print format and
source patch points so host parsing stays deterministic.

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
