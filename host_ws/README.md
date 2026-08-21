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

For the PC-side visualization graph:

```bash
bash deployment/pc/run_dashboard.sh
```

The Rock64 acquisition service publishes the ROS graph over DDS. The PC-side
launch starts the odometry TF completion, Foxglove Bridge on
`ws://127.0.0.1:8765`, and online SLAM Toolbox. Open Foxglove Desktop on the
PC and connect to that WebSocket. The existing HTTPS endpoint at
`https://192.168.1.139:9090/system` is Cockpit's external system page, not a
ROS dashboard; it is outside this repository and must not be reused for ROS or
Foxglove traffic.

The deployment service starts hardware acquisition only. The PC dashboard is
manual and read-only. Nav2 remains opt-in until the robot's odom, TF tree,
costmap parameters, and safety-gated velocity path are validated.

The historical `rock64_dashboard.launch.py` name remains as a compatibility
alias for the PC-only launch; it no longer starts hardware or heavy autonomy
on the Rock64. See [`deployment/pc/README.md`](../deployment/pc/README.md).

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
   python3 src/robot_teleop/robot_teleop/ps5_device_check.py --device /dev/input/ps5_controller
   ```

   The current deployed STM32 motor-only image intentionally reports no
   battery telemetry. Keep the safety default enabled for normal operation;
   for a raised-track bench test only, explicitly use
   `monitor_battery:=false` and restore it before production use:

   ```bash
   ros2 launch robot_bringup rock64_bringup.launch.py \
     use_teleop:=true joy_device:=/dev/input/ps5_controller \
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
