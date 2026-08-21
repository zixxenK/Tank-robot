# PC Foxglove dashboard

The PC dashboard is intentionally separate from the Rock64 acquisition
service. The Rock64 publishes hardware data over ROS 2 DDS; WSL2 Ubuntu 22.04
runs the PC-side TF completion, Foxglove Bridge, and SLAM Toolbox.

## One-time WSL2 setup

The supported PC environment is WSL2 Ubuntu 22.04 with ROS 2 Humble:

From PowerShell, use the repository wrapper so the correct WSL distribution is
selected even when Ubuntu 20.04 is the default distribution:

```powershell
.\deployment\pc\setup_dashboard.ps1
```

The equivalent command from an Ubuntu-22.04 WSL shell is:

```bash
cd /mnt/c/Projects/Tank-Robot/Tank-robot
bash deployment/pc/setup_wsl_dashboard.sh
```

On Windows 11, mirrored WSL networking is preferred because it puts WSL on the
same LAN as the Rock64 and avoids common DDS multicast/NAT failures. In
`%UserProfile%/.wslconfig`:

```ini
[wsl2]
networkingMode=mirrored
firewall=true
dnsTunneling=true
```

Run `wsl --shutdown` from PowerShell after changing that file, then restart
the WSL distribution. Windows Defender Firewall must allow the ROS 2 DDS UDP
traffic on the private robot network. Keep the Foxglove Bridge bound to
`127.0.0.1` unless remote LAN viewing is explicitly required.

Both systems must use the same domain and a non-loopback ROS setting:

```bash
export ROS_DOMAIN_ID=42
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_LOCALHOST_ONLY=0
```

If DDS discovery is unreliable under the installed WSL networking mode, use a
Fast DDS Discovery Server on the Rock64 and set `ROS_DISCOVERY_SERVER` to
`192.168.1.139:11811` on both systems. The Rock64 deployment installs this as
`rock64-fastdds-discovery.service`; keep UDP port 11811 restricted to the robot
LAN because discovery is not an authentication mechanism.

Start the optional server in a second WSL terminal:

```bash
sudo systemctl enable --now rock64-fastdds-discovery.service
export ROS_DISCOVERY_SERVER=192.168.1.139:11811
```

## Start the graph

First start or verify the Rock64 hardware service with LiDAR, HC-SR04, and
camera acquisition enabled. Then in WSL:

```bash
cd /mnt/c/Projects/Tank-Robot/Tank-robot
bash deployment/pc/run_dashboard.sh
```

From PowerShell, the equivalent wrapper is:

```powershell
.\deployment\pc\run_dashboard.ps1
```

The command starts:

- `odom_tf_broadcaster` for `odom -> base_link`;
- Foxglove Bridge on `ws://127.0.0.1:8765`;
- online SLAM Toolbox in mapping mode.

Open Foxglove Desktop on Windows and connect to:

```text
ws://127.0.0.1:8765
```

If WSL DDS cannot exchange UDP with the Rock64, use the SSH-forwarded
dashboard instead. It runs Foxglove Bridge and SLAM on the Rock64 and exposes
the read-only websocket through the existing SSH key:

```powershell
.\deployment\pc\run_dashboard_remote.ps1
```

Connect Foxglove Desktop to `ws://127.0.0.1:18765` for that mode. Keep the
PowerShell window open while using the dashboard.

The legacy command remains an alias:

```bash
ros2 launch robot_bringup rock64_dashboard.launch.py
```

It is now PC-only and does not start Rock64 hardware or move the robot.

## Mapping and localization

Keep the dashboard read-only and use the already-approved teleoperation path
to move the robot during mapping. Save a map on the PC:

```bash
mkdir -p maps/warehouse_01
ros2 run nav2_map_server map_saver_cli -f maps/warehouse_01/warehouse_01
```

Restart the dashboard against the saved map for localization:

```bash
bash deployment/pc/run_dashboard.sh \
  slam_mode:=localization \
  map_file_name="$(pwd)/maps/warehouse_01/warehouse_01"
```

Nav2 remains disabled by default. Do not pass `use_nav2:=true` until the map,
TF tree, odometry, costmaps, and safety-gateway command path have been
commissioned.

## Foxglove read-only panel preset

Use `foxglove/tank_robot_readonly_layout.json` as the authoritative panel
preset. It covers:

- `/scan` and `/map` in a 3D panel;
- `/camera/image_raw/compressed`;
- `/camera/usb/image_raw/compressed`;
- `/ultrasonic/range`;
- `/stm32/odom`, `/stm32/imu`, `/stm32/diagnostics`;
- `/lidar/diagnostics`;
- `/camera/diagnostics` and `/camera/usb/diagnostics`;
- `/safety/diagnostics`, `/teleop/ps5_status`, and `/tf`.

The bridge is also configured without Foxglove's `clientPublish` capability,
so the read-only boundary is enforced by the transport rather than only by
the panel layout. The preset contains no command or motor-service panel.
