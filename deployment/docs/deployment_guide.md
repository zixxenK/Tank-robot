# Rock64 Deployment

## Target

- Ubuntu 22.04
- ROS 2 Humble
- Canonical workspace: `host_ws`
- STM32 transport: hardened packed binary over the original Hiwonder WCH
  USB-UART link on `/dev/rock64_stm32` (USART1 PA9/PA10, 1,000,000 baud,
  8N1; product connector UART1)

## Install

From the repository root on the Rock64:

```bash
sudo bash deployment/scripts/rock64_setup.sh --ros-distro auto
```

The setup script installs dependencies, creates the STM32 udev rule, builds
`host_ws`, writes `deployment/systemd/systemd_config.conf`, and installs the
`rock64-robot.service` unit.

## Configuration

For PyCharm Professional Remote SSH setup and debugging of the Rock64-side
Python nodes, see [pycharm_remote_ssh.md](pycharm_remote_ssh.md). The guide
keeps interpreter credentials and machine-local IDE identifiers out of the
repository.

Copy and edit the template when managing configuration manually:

```bash
cp deployment/systemd/systemd_config.conf.example \
  deployment/systemd/systemd_config.conf
```

Important fields:

```text
SERIAL_PORT=/dev/rock64_stm32
USE_HARDWARE_BRIDGE=true
USE_CAMERA_BRIDGE=false
ROS_DISTRO=auto
ROS_DOMAIN_ID=42
```

There are no transport fallbacks. Startup fails when `host_ws` or the selected
hardware serial device is missing.

## Manual Build and Launch

```bash
source /opt/ros/humble/setup.bash
cd host_ws
colcon build --symlink-install
source install/setup.bash
ros2 launch robot_bringup rock64_bringup.launch.py
```

Host-only validation:

```bash
ros2 launch robot_bringup rock64_bringup.launch.py \
  use_hardware_bridge:=false use_teleop:=false
```

## Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now rock64-robot.service
systemctl status rock64-robot.service
journalctl -u rock64-robot.service -f
```

## Updating and flashing from the Rock64

From the development PC, the canonical workflow is:

```powershell
.\scripts\deploy_rock64.ps1
```

This uploads the current source tree to `rock64@rock64`, retains a backup of
the existing Rock64 source tree, builds the selected ROS packages and the
STM32 Release image on the Rock64, stops the running service, flashes through
the Rock64-connected ST-Link, performs readback verification, starts the
image through SWD, runs `python3 scripts/motor_link_safe_test.py`, and
restarts the service only after the safe UART proof passes. It always flashes
and requires both USB devices to be connected to the Rock64:

- WCH motor UART `1a86:55d4`, exposed as `/dev/rock64_stm32` and connected to
  the physical UART1 connector / USART1 PA9-PA10
- ST-Link `0483:3748`, used only for SWD flashing

The board-side command is also available directly after source deployment:

```bash
bash /opt/rock64-robot/deployment/scripts/rock64_update_and_flash.sh
```

If the board reset is not asserted automatically by the ST-Link, press the
STM32 board reset button after the verified flash and before motion testing.

Expected control nodes are:

- `/safety_gateway`
- `/ps5_ros_bridge` when teleop is enabled
- `/stm32_hardened_bridge` when hardware is enabled

Before enabling motor power, complete the preflight and raised-track checks in
`docs/HARDWARE_VALIDATION.md`.

For a dedicated raised-track motor check, run:

```bash
make host-motor-test
```

That launch path keeps teleop disabled and exercises the tread pair mapped to
motor IDs 0 and 1 on the STM32 bridge, which correspond to the M1/M2 motor
controller outputs.
