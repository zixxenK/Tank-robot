# LM Studio Integration

The LM Studio bridge runs in WSL Ubuntu 22.04, not on the Rock64. Keep the
server base URL and exact loaded model identifier in shell environment variables
so an old model name cannot remain hidden in source or operator documentation.
The default WSL address below is reachable from WSL; use the development-PC
address when the ROS node is run across the Rock64 network.

## Interfaces

The three executables are intentionally independent:

- `lmstudio_codegen` consumes `/agent/codegen/request` and writes review-only
  Markdown proposals under `/tmp/tank_robot_codegen_proposals`. It never runs
  generated code.
- `lmstudio_diagnostics` aggregates `/safety/diagnostics`,
  `/stm32/diagnostics`, both camera diagnostic topics, `/hardware_test/diagnostics`,
  `/lidar/diagnostics`, and the compatibility `/diagnostics` topic. It answers
  explicit requests received on `/agent/diagnostics/request` and has no
  command publisher. The compatibility topic remains subscribed so older
  diagnostic producers can still be explained while current nodes migrate to
  component-specific diagnostic topics.
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
export LM_STUDIO_BASE_URL='http://192.168.56.1:1234'
export LM_STUDIO_MODEL='exact-loaded-model-id'
export ROS_DOMAIN_ID=42
cd /mnt/c/Projects/Tank-Robot/Tank-robot/host_ws
source ../deployment/scripts/source_host_ws.sh
colcon build --symlink-install
source ../deployment/scripts/source_host_ws.sh
ros2 run agent_core lmstudio_diagnostics --ros-args \
  -p base_url:="${LM_STUDIO_BASE_URL}" \
  -p model:="${LM_STUDIO_MODEL}"
```

Start code generation and teleop in separate terminals only when needed. Keep
teleop stopped until the raised-track hardware validation gate passes.

```bash
ros2 run agent_core lmstudio_codegen
ros2 run agent_core lmstudio_teleop
```

If LM Studio reports an unknown model, copy the exact identifier shown by its
loaded-models view into `LM_STUDIO_MODEL` and rerun the command. Do not encode
that identifier as a new repository default.
