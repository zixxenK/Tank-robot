# host_ws

This directory is the canonical ROS 2 host workspace for Rock64-side code.

`host_ws/src` is the canonical ROS 2 source tree. All maintained host packages
should be created or updated there.

Build from this folder:

   ```bash
   cd host_ws
   colcon build --symlink-install
   ```

Verify bringup:

   ```bash
   source install/setup.bash
   ros2 launch robot_bringup rock64_bringup.launch.py
   ```
