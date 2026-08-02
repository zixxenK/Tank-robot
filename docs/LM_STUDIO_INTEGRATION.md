# LM Studio Integration

The LM Studio bridge runs in WSL Ubuntu 22.04, not on the Rock64. The supplied
`192.168.56.1:1234` address is reachable from WSL but is not routed to the
Rock64 Ethernet network.

## Interfaces

The three executables are intentionally independent:

- `lmstudio_codegen` consumes `/agent/codegen/request` and writes review-only
  Markdown proposals under `/tmp/tank_robot_codegen_proposals`. It never runs
  generated code.
- `lmstudio_diagnostics` consumes `/diagnostics` and answers explicit requests
  received on `/agent/diagnostics/request`. It has no command publisher.
- `lmstudio_teleop` consumes `/agent/chat/request` and
  `/agent/voice/transcript`. Commands last at most one second and publish only
  to `/agent/cmd_vel_proposed` with `/agent/heartbeat`; `safety_gateway` still
  owns clamping, battery checks, e-stop, and the hardware output topic.

The voice topic expects text from a separate speech-to-text process. This
package does not capture microphone audio.

## Start In WSL

Authentication is enabled on the LM Studio server. Enter the token directly in
the WSL shell, not in source files or chat:

```bash
export LM_API_TOKEN='token-entered-locally'
export ROS_DOMAIN_ID=42
cd /mnt/c/Projects/Tank-Robot/Tank-robot/host_ws
source /opt/ros/humble/setup.bash
colcon build --packages-select agent_core --symlink-install
source install/setup.bash
ros2 run agent_core lmstudio_diagnostics --ros-args \
  -p base_url:=http://192.168.56.1:1234 \
  -p model:=prism-ml/bonsai-27b
```

Start code generation and teleop in separate terminals only when needed. Keep
teleop stopped until the raised-track hardware validation gate passes.

```bash
ros2 run agent_core lmstudio_codegen
ros2 run agent_core lmstudio_teleop
```

Confirm the exact loaded model identifier with the authenticated models API if
LM Studio reports that `prism-ml/bonsai-27b` is unknown.