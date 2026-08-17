# Rock64 Deployment

## Target

- Ubuntu 22.04
- ROS 2 Humble
- Canonical workspace: `host_ws`
- STM32 transport: hardened packed binary over the original Hiwonder WCH
  USB-UART master link on `/dev/rock64_stm32` (USART3 PD8/PD9, 1,000,000 baud,
  8N1; factory labels DBG_TX/DBG_RX)

## Install

From the repository root on the Rock64:

```bash
sudo bash deployment/scripts/rock64_setup.sh --ros-distro auto
```

The setup script installs dependencies, creates the STM32 udev rule, builds
`host_ws`, writes `deployment/systemd/systemd_config.conf`, and installs the
`rock64-robot.service` unit.

## Configuration

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
