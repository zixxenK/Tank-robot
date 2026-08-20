# Rock64 Ranger Tank Robot

A differential-drive robot with an STM32F407 motor controller, a Rock64 ROS 2
Humble host, and an optional ESP32 camera.

The validated 1.0 hardware/software contract is recorded in
[docs/SOURCE_OF_TRUTH_1_0.md](docs/SOURCE_OF_TRUTH_1_0.md). Read that before
changing UART ownership, flashing, or selecting hardware profiles.

## Control Architecture

```text
PS5 DualSense (optional) ─> /cmd_vel ──────┐
                                               v
Agent ──> /agent/cmd_vel_proposed ──> safety_gateway
Agent heartbeat ────────────────────────────> │
E-stop + battery telemetry ─────────────────> │
                                               v
                                  /ranger/cmd_vel_safe
                                               v
                                  stm32_hardened_bridge
                                               v
                              USART1/WCH packed binary (product UART1)
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

There is one ROS workspace (`host_ws`) and one production motor transport:
packed binary over USART1 (PA9/PA10) through the WCH USB-UART adapter on the
product-labeled UART1 connector. This mapping is the 1.0 source of truth;
USART3/PD8-PD9 is retained only in the stock 7in1 reference material.
Native USB CDC is diagnostic-only
and ST-Link is flash/debug-only. Legacy ASCII bridges, duplicate workspaces,
and placeholder micro-ROS paths have been removed.

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

The production firmware has one host-UART mapping. Do not select or hand-edit
an alternate host UART; the stock USART3/PD8-PD9 mapping belongs only to the
7in1 reference material.

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

Hardware / manual motor test:

```bash
source /opt/ros/humble/setup.bash
source host_ws/install/setup.bash
scripts/robot_base_start.sh
```

PS5 is optional. The default launch starts the Rock64/ROS 2/STM32 base without
teleoperation. Send exactly one of these commands when you are ready to test:

```bash
ros2 topic pub --once /stm32/test_direction std_msgs/msg/String "{data: forward}"
ros2 topic pub --once /stm32/test_direction std_msgs/msg/String "{data: back}"
ros2 topic pub --once /stm32/test_direction std_msgs/msg/String "{data: stop}"
```

Equivalent Rock64 movement scripts are provided. Start the base in one
terminal, then run the requested movement in another:

```bash
scripts/motor_forward.sh --confirm
scripts/motor_stop.sh
scripts/motor_back.sh --confirm
scripts/motor_stop.sh
```

To run that complete sequence automatically:

```bash
scripts/motor_test_sequence.sh --confirm 1
```

`stop` is also sent automatically when the bridge reconnects or shuts down.
Use `use_teleop:=true` only when a PS5 controller is connected.

Host-only launch preparation uses:

```bash
ros2 launch robot_bringup rock64_bringup.launch.py \
  use_hardware_bridge:=false use_teleop:=false
```

The hardware preflight fails before node startup when the configured serial
device or required PS5 joystick does not exist. The default devices are
`/dev/rock64_stm32` and `/dev/input/js0`; set `SERIAL_PORT` or
`PS5_JOY_DEVICE` when the Rock64 enumerates different paths.

With tracks lifted and motor power deliberately enabled, prove each motor
through the single ROS 2 bridge:

```bash
ros2 service call /stm32/motor_1/enable std_srvs/srv/SetBool "{data: true}"
ros2 service call /stm32/motor_1/enable std_srvs/srv/SetBool "{data: false}"
ros2 service call /stm32/motor_2/enable std_srvs/srv/SetBool "{data: true}"
ros2 service call /stm32/motor_2/enable std_srvs/srv/SetBool "{data: false}"
```

The service test owns the motor pair until both are stopped, and runs at the
guarded `motor_test_speed` (0.10 normalized by default). For a pre-ROS proof,
use `python3 scripts/motor_start_stop_test.py --confirm`.

## Configuration

- Safety policy: `host_ws/src/agent_core/config/safety_gateway.yaml`
- Hardware parameters: `host_ws/src/robot_bringup/config/rock64_hardware.yaml`
- Deployment template: `deployment/systemd/systemd_config.conf.example`
- Stable STM32 device: `/dev/rock64_stm32` -> WCH `/dev/ttyACM*` (WCH
  VID:PID `1a86:55d4`); ST-Link `0483:3748` is flash/debug-only.

A critical-battery stop is latched. It can be cleared only after fresh telemetry
stays above the recovery threshold and the operator e-stop is clear:

```bash
ros2 service call /safety/reset_battery_latch std_srvs/srv/Trigger {}
```

## Deployment

For the recommended PyCharm Professional Remote SSH workflow for Rock64-side
ROS 2 Python development, see
[deployment/docs/pycharm_remote_ssh.md](deployment/docs/pycharm_remote_ssh.md).

```bash
sudo bash deployment/scripts/rock64_setup.sh --ros-distro auto
```

The setup script targets Ubuntu 22.04/Humble, builds `host_ws`, installs the
udev rule and systemd service, and launches only the hardened STM32 bridge.

To send the current checkout to the board and perform the complete update from
the Rock64 (including the STM32 ST-Link flash), run this from Windows with an
SSH key configured for `rock64@rock64`:

```powershell
.\scripts\deploy_rock64.ps1
```

The script preserves a source backup on the Rock64, builds the ROS packages and
STM32 Release image there, flashes and verifies the STM32 through the Rock64
ST-Link, starts the image with SWD, runs the safe stop/zero-speed UART proof,
and restarts the robot service only after every step passes. The Rock64 sudo
password is requested interactively and is never stored. This workflow always
flashes; source-only synchronization is intentionally not supported by this
command.

## Hardware Gate

Firmware builds and host/mock tests are pre-flash checks. Before operating the
robot, complete [docs/HARDWARE_VALIDATION.md](docs/HARDWARE_VALIDATION.md),
including raised-track direction tests, all encoder channels, the 250 ms
command timeout, battery thresholds, reconnect behavior, and a controlled
soak test.
