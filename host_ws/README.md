# host_ws

This directory is the canonical ROS 2 host workspace for Rock64-side code.

## Current migration state

- Existing packages still live in `../ros2_ws/src` for backward compatibility.
- New host-side packages should be created under `host_ws/src`.
- Deployment scripts automatically prefer `host_ws` when `host_ws/src` exists.

## Recommended migration

1. Copy packages from `ros2_ws/src` into `host_ws/src`.
2. Build from this folder:
   ```bash
   cd host_ws
   colcon build --symlink-install
   ```
3. Verify bringup:
   ```bash
   source install/setup.bash
   ros2 launch robot_bringup rock64_bringup.launch.py
   ```

If `host_ws/src` is empty, scripts still fall back to `ros2_ws`.
