# host_ws

This directory is the canonical ROS 2 host workspace for Rock64-side code.

`host_ws/src` is the canonical ROS 2 source tree. All maintained host packages
should be created or updated there.

The directly connected STL-50B2 LiDAR uses ROCK64 UART2 on header pins 8/10
and the required synchronization input on pin 12. Build and launch it with:

```bash
colcon build --symlink-install --packages-select robot_drivers robot_bringup
source install/setup.bash
ros2 launch robot_bringup stl50b2.launch.py
```

See [`docs/lidar_scanner/STL-50B2_ROCK64.md`](../docs/lidar_scanner/STL-50B2_ROCK64.md)
for UART2 device-tree and GPIO validation.

For the combined Rock64 visualization graph:

```bash
ros2 launch robot_bringup rock64_dashboard.launch.py \
  use_lidar:=true use_camera_bridge:=true use_usb_camera:=true \
  use_slam:=true use_nav2:=false use_rviz:=true
```

This exposes ROS topics through rosbridge on port 9091. The existing HTTPS
endpoint at `https://192.168.1.139:9090/system` is Cockpit's system page, not a
ROS dashboard and is not implemented in this repository. It cannot display
`/scan` or camera topics merely because ROS nodes are running. A ROS-aware
frontend must connect to `ws://192.168.1.139:9091` (or a reverse proxy must
forward that WebSocket); port 9090 should not be reused for rosbridge.

The deployment service currently starts the canonical hardware bringup only.
The combined dashboard graph is intentionally manual and deferred while the
sensor links are commissioned. Nav2 remains opt-in until the robot's odom, TF
tree, costmap parameters, and safety-gated velocity path are validated.

Build from this folder:

   ```bash
   cd host_ws
   colcon build --symlink-install
   ```

Verify bringup:

   ```bash
   source install/setup.bash
   ros2 launch robot_bringup rock64_bringup.launch.py use_teleop:=true
   ```

   The PS5 readiness check accepts either spelling:

   ```bash
   python3 src/robot_teleop/robot_teleop/ps5_device_check.py --device /dev/input/js0
   ```

   The current deployed STM32 motor-only image intentionally reports no
   battery telemetry. Keep the safety default enabled for normal operation;
   for a raised-track bench test only, explicitly use
   `monitor_battery:=false` and restore it before production use:

   ```bash
   ros2 launch robot_bringup rock64_bringup.launch.py \
     use_teleop:=true joy_device:=/dev/input/js0 \
     serial_port:=/dev/rock64_stm32 monitor_battery:=false
   ```

## LM Studio integration

LM Studio runs on the development PC, not on the Rock64. Start its local
server, load the exact model identifier shown by LM Studio, and make port
`1234` reachable from the Rock64. Verify from the PC first:

```bash
curl http://localhost:1234/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"model":"nvidia/nemotron-3-nano-4b","input":"Reply with OK."}'
```

Then verify from the Rock64 using the development PC address (never
`localhost` on the Rock64):

```bash
curl http://<DEVELOPMENT-PC-IP>:1234/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"model":"nvidia/nemotron-3-nano-4b","input":"Reply with OK."}'
```

Run the safety-gated AI node only after that check succeeds:

```bash
ros2 run agent_core lmstudio_teleop --ros-args \
  -p base_url:=http://<DEVELOPMENT-PC-IP>:1234 \
  -p model:=nvidia/nemotron-3-nano-4b
```

The Hugging Face MCP and weather examples are LM Studio API feature tests;
they are not required for robot teleoperation. The robot client uses the
native chat endpoint for text and the Responses endpoint for the constrained
`move_robot` tool, while the safety gateway remains the final motion gate.
