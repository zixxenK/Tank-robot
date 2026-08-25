# Rock64 Ranger Tank Robot

A differential-drive robot with an STM32F407 motor controller, a Rock64 ROS 2
Humble host, and paired ESP32/USB cameras.

The validated 1.0 hardware/software contract is recorded in
[docs/SOURCE_OF_TRUTH_1_0.md](docs/SOURCE_OF_TRUTH_1_0.md). Read that before
changing UART ownership, flashing, or selecting hardware profiles.

## One-Shot E2E Mission

For normal development and operator validation, use the single mission command:

```bash
./run_e2e.sh
```

On Windows PowerShell:

```powershell
.\run_e2e.ps1
```

Equivalent Make target:

```bash
make e2e
```

The mission runner performs environment setup, offline full-stack contract
tests, available firmware and ROS builds, safe non-motion Rock64 hardware
acceptance when the robot service is present, and cleanup. Build and test logs
are captured under `log/e2e/`; the console shows only the Tank-Robot System
Report with overall status, subsystem status, anomalies, and next steps.

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
command-timed-out, optionally battery-gated after ADC calibration, and
emergency-stopped. Autonomous commands
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

Rock64 Pi-2 header wiring for direct Rock64 sensors is documented in
[docs/ROCK64_PI2_BUS_PINOUT.md](docs/ROCK64_PI2_BUS_PINOUT.md). The STM32 motor
controller remains on the validated WCH USB-UART `/dev/rock64_stm32` path.

## STM32 Build

The firmware uses ARM GNU Toolchain and Ninja:

```powershell
cd firmware/stm32_chassis
cmake --preset Debug
cmake --build --preset Debug --parallel 4
```

Release build:

```powershell
cmake --preset Release
cmake --build --preset Release --parallel 4
```

The production firmware has one host-UART mapping. Do not select or hand-edit
an alternate host UART; the stock USART3/PD8-PD9 mapping belongs only to the
7in1 reference material.

Generated images are under `firmware/stm32_chassis/build/<preset>/`. Building
does not flash the controller.

Firmware flashing is never performed directly from a PC. Use
`.\scripts\deploy_rock64.ps1` from Windows or
`bash deployment/scripts/rock64_update_and_flash.sh` on the Rock64 so the
updated robot host owns ST-Link access, readback verification, and the safe
UART proof.

## Host Build and Test

Target environment: Ubuntu 22.04 with ROS 2 Humble.

The preferred host validation path is the one-shot mission runner above. For
focused package work, the lower-level commands remain available:

```bash
source deployment/scripts/source_host_ws.sh
cd "$HOST_WS_PATH"
colcon build --symlink-install
source deployment/scripts/source_host_ws.sh
colcon test
colcon test-result --verbose
```

Windows-only policy tests use the repository stubs:

```powershell
$env:PYTHONPATH = "$(Resolve-Path stubs);$(Resolve-Path host_ws/src/agent_core);$(Resolve-Path host_ws/src/robot_drivers)"
python -m pytest host_ws/src/agent_core/test host_ws/src/robot_drivers/test -q
```

Offline launch and ROS-shim contract tests are also available without a ROS
installation. The repository test configuration supplies the offline import
paths and excludes generated ROS build/install trees:

```powershell
python -m pytest -q
```

## Bringup

After the STM32 firmware and ROS workspace have been deployed, validate the
robot through the non-motion E2E mission:

```bash
./run_e2e.sh
```

For persistent operation after validation, start the complete Rock64 hardware
graph with:

```bash
bash scripts/onecmd.sh
```

For focused hardware diagnostics, run every non-motion acceptance stage in
order with:

```bash
bash scripts/hardware_acceptance.sh
```

For the complete independent M1/M2 proof, securely raise both tracks first,
then use `bash scripts/hardware_acceptance.sh --tracks-raised`. The runner
checks fresh STM32, encoder, odometry, onboard IMU, PS5, ESP32-camera, and
USB-camera data before any optional raised-track motor stage, prints a numbered PASS/FAIL table,
always stops both motors, and writes a JSON report. See
[the exact Rock64 procedure](docs/ROCK64_HARDWARE_ACCEPTANCE.md).

The project runtime assumes the onboard IMU is a QMI8658, but Hiwonder's
current product/hardware text says MPU6050 while its program-analysis chapter
3.5 says QMI8658. See the [complete board audit](docs/HIWONDER_ROS_ROBOT_CONTROLLER_V1_2.md).
The production STM32 path uses I2C2 at 400 kHz on PB10/PB11, probes 7-bit
address `0x6A` or `0x6B`, and requires register `0x00` (`WHO_AM_I`) to return
`0x05`; that runtime result is the physical identity proof. The retired MPU
driver and FIFO path are not part of the build.

The older individual commissioning commands remain available only as guarded
maintenance exceptions for raised-track bench work. They are not a normal
operator motion path; normal driving is always PS5/agent -> safety gateway ->
hardened STM32 bridge. Send exactly one of these only when a single direction
test is needed:

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

The hardware preflight fails before node startup when the configured STM32
serial device does not exist. The PS5 bridge supports hot-plug and waits when
the controller is off. The stable defaults are `/dev/rock64_stm32` and
`/dev/input/ps5_controller`; set `SERIAL_PORT` or `PS5_JOY_DEVICE` only when
the Rock64 uses different persistent paths.

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
sudo bash deployment/scripts/rock64_setup.sh --ros-distro humble
```

The setup script targets Ubuntu 22.04/Humble, builds `host_ws`, installs the
udev rules and systemd service, and enables the complete hardware acquisition
graph. Individual components remain configurable through
`deployment/systemd/systemd_config.conf`.

To send the current checkout to the board and perform the complete update from
the Rock64 (including the STM32 ST-Link flash), run this from Windows with an
SSH key configured for `rock64@rock64`:

```powershell
.\scripts\deploy_rock64.ps1
```

For source/configuration and ROS host updates without programming either
controller, use:

```powershell
.\scripts\sync_rock64_safe.ps1 -RestartService
```

For the normal all-in-one PC operator workflow (sync, Rock64 rebuild,
service restart, and read-only dashboard), use:

```powershell
.\deployment\pc\robot_ready.ps1
```

The Rock64 systemd service is enabled at setup and starts the hardware graph
automatically after the board powers on. For automatic deployment of tested
local changes, commit them and run
`.\deployment\pc\watch_commits_and_sync.ps1`; it intentionally does not
deploy uncommitted edits or flash firmware unattended.

The script preserves a source backup on the Rock64, builds the ROS packages and
STM32 Release image there, flashes and verifies the STM32 through the Rock64
ST-Link, starts the image with SWD, runs the safe stop/zero-speed UART proof,
and restarts the robot service only after every step passes. The Rock64 sudo
password is requested interactively and is never stored. The flashing workflow
above always flashes; use `sync_rock64_safe.ps1` for source-only
synchronization.

## Hardware Gate

The optional distance sensor is the Hiwonder Glowy RGB ultrasonic module. It
is documented in [docs/GLOWY_ULTRASONIC_BUILD_PATH.md](docs/GLOWY_ULTRASONIC_BUILD_PATH.md)
and plugs into the controller's four-pin `5V/GND/SDA/SCL` I2C connector at
address `0x77`. It is not part of the current drive/camera/IMU gate; no
Arduino or pulse-timing adapter is required when it is later enabled.

Firmware builds and host/mock tests are pre-flash checks. Before operating the
robot, follow the single current procedure in
[docs/OPERATOR_GUIDE.md](docs/OPERATOR_GUIDE.md). The detailed
[docs/HARDWARE_VALIDATION.md](docs/HARDWARE_VALIDATION.md) remains a technical
appendix for raised-track, timeout, reconnect, and future accessory checks.
