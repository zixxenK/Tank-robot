# Rock64 Ranger — Deployment Guide

## Overview

The `deployment/` directory contains the Infrastructure-as-Code layer that
enables hands-free robot startup via systemd on the Rock64 SBC.

## Directory Structure

```text
deployment/
├── systemd/
│   ├── rock64-robot.service        # systemd unit file
│   └── systemd_config.conf.example # configuration template
├── scripts/
│   ├── rock64_setup.sh   # full setup & installation
│   ├── apply_systemd.sh  # install/restart systemd service only
│   ├── robot_start.sh    # ROS2 launch orchestrator (called by systemd)
│   └── source_ros2_ws.sh # ROS2 distro auto-detection & sourcing
└── docs/
    └── deployment_guide.md  # this file
```

## Serial Device

The STM32 motor controller connects via a **QinHeng CH552 USB-CDC adapter**
(`USB ID 1a86:55d4`).  The udev rule installed by `rock64_setup.sh` and
`create_udev_rules.sh` creates the stable symlink `/dev/rock64_stm32`.

To find the persistent by-id path after the device is plugged in:

```bash
ls -l /dev/serial/by-id/ | grep 1a86
# Example output:
# usb-1a86_USB_Single_Serial_5C67041071-if00 -> ../../ttyACM0
```

You can use either `/dev/rock64_stm32` (symlink) or the full `by-id` path in
`SERIAL_PORT` — both are stable across reboots.

## First-Time Setup

Prerequisite: Rock64 must run Ubuntu 22.04 (Humble).
Ubuntu 24.04/26.04 and other variants are not supported by this repository policy.

```bash
# 1. Clone the repo to the Rock64
git clone https://github.com/zixxenK/Tank-robot /opt/rock64-robot
cd /opt/rock64-robot

# 2. Run the setup script (installs ROS2, builds workspace, installs service)
#    Use the stable symlink name (created by the udev rule installed below):
sudo bash deployment/scripts/rock64_setup.sh \
  --ros-distro auto \
  --serial-port /dev/rock64_stm32 \
  --camera-ip 192.168.1.125

# 3. Verify the udev symlink was created (replug USB cable if needed):
ls -l /dev/rock64_stm32
```

Workspace resolution used by deployment scripts:

1. If `HOST_WS_PATH` is set, use that path.
2. Else if `host_ws/src` exists, use `host_ws`.
3. Else fallback to `ros2_ws`.

This allows non-breaking migration from `ros2_ws` to `host_ws`.

## Re-installing the Service Only

```bash
sudo bash deployment/scripts/apply_systemd.sh
```

## Service Management

```bash
sudo systemctl status  rock64-robot.service
sudo systemctl start   rock64-robot.service
sudo systemctl stop    rock64-robot.service
sudo systemctl restart rock64-robot.service

# View logs
journalctl -u rock64-robot.service -f
```

## Configuration

Copy and edit the template:

```bash
cp deployment/systemd/systemd_config.conf.example \
   deployment/systemd/systemd_config.conf
# Edit values, then re-run apply_systemd.sh
```

Key variables in `systemd_config.conf`:

| Variable | Default | Purpose |
|---|---|---|
| `SERIAL_PORT` | `/dev/rock64_stm32` | STM32 serial device |
| `USE_MICRO_ROS` | `false` | Enable micro-ROS agent mode |
| `USE_LEGACY_BRIDGES` | `true` | Enable Python serial bridge mode |
| `MICRO_ROS_DEV` | same as `SERIAL_PORT` | Device for micro-ROS agent |
| `USE_CAMERA_BRIDGE` | `false` | Enable ESP32 camera bridge |

## ROS2 Distro Auto-Detection

`source_ros2_ws.sh` maps Ubuntu LTS → ROS2 distro:

| Ubuntu | ROS2 Distro |
|--------|-------------|
| 22.x   | Humble      |

## Final Testing Checklist (First Drive)

### Step 1 — Verify serial device

```bash
# After plugging in the USB cable:
ls -l /dev/rock64_stm32        # must exist
ls -l /dev/serial/by-id/ | grep 1a86   # persistent by-id path
```

If `/dev/rock64_stm32` is missing, rerun udev setup:

```bash
sudo bash host_ws/src/ros_robot_controller/scripts/create_udev_rules.sh
# or replug the USB cable after the rule is installed
```

### Step 2 — Build the workspace

```bash
cd /opt/rock64-robot
make host-build
```

### Step 3 — Launch hardware bringup (legacy serial bridge, robot on stand)

```bash
make host-hardware
# or equivalently:
# bash scripts/unify_host_ws.sh --mode hardware --no-install-deps
```

Expected nodes:
```bash
ros2 node list
# /ps5_ros_bridge
# /stm32_serial_bridge
```

Expected topics:
```bash
ros2 topic list
# /cmd_vel
# /tracks/left_cmd
# /tracks/right_cmd
```

### Step 4 — Teleop safety test (tracks off the ground)

In a second terminal:

```bash
make host-teleop-ps5   # PS5 DualSense
# or
make host-teleop       # keyboard (WASD)
```

Verify `/cmd_vel` changes:

```bash
ros2 topic echo /cmd_vel
```

Move left stick / press W — expect `linear.x` to change.

### Step 5 — Verify motor commands reach STM32

```bash
ros2 topic echo /tracks/left_cmd
ros2 topic echo /tracks/right_cmd
```

With low speed input, expect non-zero values in both topics.

### Step 6 — Motor bringup sequence (still on stand)

```bash
ros2 launch robot_bringup rock64_bringup.launch.py \
  use_legacy_bridges:=true \
  run_motor_bringup_test:=true
```

Watch that both tracks spin in the correct directions for each phase
(left_forward, left_reverse, right_forward, right_reverse).

### Step 7 — Floor test (only after steps 1–6 pass)

Place robot on floor. Use teleop at low speed:
- Short forward / reverse run.
- Turn-in-place left and right.
- Verify emergency stop by releasing sticks → robot stops within `cmd_timeout` (0.25 s).

### Step 8 — micro-ROS mode (optional, requires micro-ROS firmware on STM32)

Edit `deployment/systemd/systemd_config.conf`:

```
USE_MICRO_ROS=true
USE_LEGACY_BRIDGES=false
MICRO_ROS_DEV=/dev/rock64_stm32
```

Restart service:

```bash
sudo systemctl restart rock64-robot.service
journalctl -u rock64-robot.service -f
```

Verify micro-ROS agent connects and STM32 nodes appear:

```bash
ros2 node list   # expect STM32 micro-ROS nodes
ros2 topic list  # expect /cmd_vel, /odom, etc.
```
