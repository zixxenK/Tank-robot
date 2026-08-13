# Rock64 Ranger Tank Robot

A differential-drive robot with an STM32F407 motor controller, a Rock64 ROS 2
Humble host, and an optional ESP32 camera.

## Control Architecture

```text
PS5 / keyboard ──> /cmd_vel ───────────────┐
                                               v
Agent ──> /agent/cmd_vel_proposed ──> safety_gateway
Agent heartbeat ────────────────────────────> │
E-stop + battery telemetry ─────────────────> │
                                               v
                                  /ranger/cmd_vel_safe
                                               v
                                  stm32_hardened_bridge
                                               v
                                  USB CDC packed binary
                                               v
                                        STM32F407
```

The STM32 bridge never subscribes to raw command topics. Teleoperation remains
available without an autonomous-agent heartbeat, but all commands are clamped,
command-timed-out, battery-gated, and emergency-stopped. Autonomous commands
also require a fresh `True` heartbeat.

## Repository Layout

```text
firmware/stm32_chassis/   STM32F407 firmware and ARM CMake build
firmware/esp32_sensors/   ESP32 camera firmware
host_ws/src/              Canonical ROS 2 workspace
host_ws/src/agent_core/   Safety gateway and configuration
host_ws/src/robot_drivers Hardened STM32 and camera bridges
deployment/               Rock64 setup and systemd integration
docs/                     Current architecture and validation documents
```

There is one ROS workspace (`host_ws`) and one STM32 transport (packed binary
over the native USB CDC interface configured by
`RosRobotControllerM4factory.ioc`). Legacy ASCII bridges, duplicate workspaces, and placeholder
micro-ROS paths have been removed.

## STM32 Build

The firmware uses ARM GNU Toolchain and Ninja:

```powershell
cd firmware/stm32_chassis
cmake --preset Debug
cmake --build --preset Debug -j 4
```

Release build:

```powershell
cmake --preset Release
cmake --build --preset Release -j 4
```

Generated images are under `firmware/stm32_chassis/build/<preset>/`. Building
does not flash the controller.

## Host Build and Test

Target environment: Ubuntu 22.04 with ROS 2 Humble.

```bash
source /opt/ros/humble/setup.bash
cd host_ws
colcon build --symlink-install
colcon test
colcon test-result --verbose
```

Windows-only policy tests use the repository stubs:

```powershell
$env:PYTHONPATH = "$(Resolve-Path stubs);$(Resolve-Path host_ws/src/agent_core);$(Resolve-Path host_ws/src/robot_drivers)"
python -m pytest host_ws/src/agent_core/test host_ws/src/robot_drivers/test -q
```

## Bringup

Hardware:

```bash
source /opt/ros/humble/setup.bash
source host_ws/install/setup.bash
ros2 launch robot_bringup rock64_bringup.launch.py
```

Host-only launch preparation uses:

```bash
ros2 launch robot_bringup rock64_bringup.launch.py \
  use_hardware_bridge:=false use_teleop:=false
```

The hardware preflight fails before node startup when the configured serial
device does not exist.

## Configuration

- Safety policy: `host_ws/src/agent_core/config/safety_gateway.yaml`
- Hardware parameters: `host_ws/src/robot_bringup/config/rock64_hardware.yaml`
- Deployment template: `deployment/systemd/systemd_config.conf.example`
- Stable STM32 device: `/dev/rock64_stm32` -> native `/dev/ttyACM*` (STM32
  VID:PID `0483:5740`)

A critical-battery stop is latched. It can be cleared only after fresh telemetry
stays above the recovery threshold and the operator e-stop is clear:

```bash
ros2 service call /safety/reset_battery_latch std_srvs/srv/Trigger {}
```

## Deployment

```bash
sudo bash deployment/scripts/rock64_setup.sh --ros-distro auto
```

The setup script targets Ubuntu 22.04/Humble, builds `host_ws`, installs the
udev rule and systemd service, and launches only the hardened STM32 bridge.

## Hardware Gate

Firmware builds and host/mock tests are pre-flash checks. Before operating the
robot, complete [docs/HARDWARE_VALIDATION.md](docs/HARDWARE_VALIDATION.md),
including raised-track direction tests, all encoder channels, command and
heartbeat timeouts, watchdog reset, battery thresholds, reconnect behavior,
and a controlled soak test.
