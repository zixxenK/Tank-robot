# deployment/docs/deployment_guide.md

# Rock64 Ranger — Deployment Guide

## Overview

The `deployment/` directory contains the Infrastructure-as-Code layer that
enables hands-free robot startup via systemd on the Rock64 SBC.

## Directory Structure

```
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

## First-Time Setup

Prerequisite: Rock64 must run Ubuntu 24.04 (Jazzy) or 22.04 (Humble).
Ubuntu 26.04/Armbian resolute is not supported by the packaged ROS2 install path.

```bash
# 1. Clone the repo to the Rock64
git clone https://github.com/zixxenK/Tank-robot /opt/rock64-robot
cd /opt/rock64-robot

# 2. Run the setup script (installs ROS2, builds workspace, installs service)
sudo bash deployment/scripts/rock64_setup.sh \
  --ros-distro auto \
  --serial-port /dev/rock64_stm32 \
  --camera-ip 192.168.1.153
```

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

## ROS2 Distro Auto-Detection

`source_ros2_ws.sh` maps Ubuntu LTS → ROS2 distro:

| Ubuntu | ROS2 Distro |
|--------|-------------|
| 24.x   | Jazzy       |
| 22.x   | Humble      |
