# PyCharm Remote SSH: Rock64 Host Workspace

This guide configures PyCharm Professional to edit and debug the canonical
Rock64 ROS 2 Python workspace over SSH. It deliberately does not store SSH
credentials, private keys, or machine-specific `.idea` interpreter IDs in the
repository.

## Prerequisites

The Rock64 must be reachable as `rock64` and already have the production host
environment installed:

```bash
sudo bash deployment/scripts/rock64_setup.sh --ros-distro humble
```

The target environment is Ubuntu 22.04 with ROS 2 Humble. Confirm the account
and workspace before configuring PyCharm:

```bash
ssh rock64@rock64
source /opt/rock64-robot/deployment/scripts/source_host_ws.sh
cd "$HOST_WS_PATH"
ros2 pkg prefix robot_drivers
python3 -c 'import rclpy, serial; print("Rock64 Python environment OK")'
```

Configure an SSH key for `rock64@rock64` rather than placing a password in an
IDE configuration. The existing Windows deployment command uses the same SSH
target:

```powershell
.\scripts\deploy_rock64.ps1
```

## Configure the interpreter

1. Open the repository root in PyCharm Professional.
2. Open **Settings | Project | Python Interpreter**, choose **Add Interpreter |
   On SSH**, and select the existing OpenSSH key for `rock64@rock64`.
3. Set the remote Python executable to `/usr/bin/python3` (or the path returned
   by `command -v python3` on the Rock64).
4. Use `/opt/rock64-robot/host_ws` as the remote workspace path.
5. Add a path mapping from the local repository `host_ws/src` to
   `/opt/rock64-robot/host_ws/src`.

Do not create a virtual environment for ROS packages unless it is explicitly
provisioned with the system ROS bindings. `rclpy` and the serial transport are
provided by the Rock64 system environment.

## ROS environment for runs and debugging

PyCharm's SSH interpreter starts non-login processes, so source ROS and the
workspace before launching a node. Configure a PyCharm Python run/debug
configuration with:

- **Script path:** the selected package script under
  `/opt/rock64-robot/host_ws/src`
- **Working directory:** `/opt/rock64-robot/host_ws`
- **Environment variables:** `ROS_DOMAIN_ID=42`,
  `SERIAL_PORT=/dev/rock64_stm32`
- **Interpreter options / wrapper:**

```bash
bash -lc 'source /opt/rock64-robot/deployment/scripts/source_host_ws.sh && exec python3 "$@"' --
```

For normal bringup, use the existing ROS launch command from an SSH terminal
instead of debugging individual processes:

```bash
source /opt/rock64-robot/deployment/scripts/source_host_ws.sh
ros2 launch robot_bringup rock64_bringup.launch.py
```

Use this host-only command when validating Python changes without hardware:

```bash
ros2 launch robot_bringup rock64_bringup.launch.py \
  use_hardware_bridge:=false use_teleop:=false
```

## Safe development workflow

1. Make and debug host-side changes through the SSH interpreter.
2. Run host tests on the Rock64:

   ```bash
   source /opt/rock64-robot/deployment/scripts/source_host_ws.sh
   cd "$HOST_WS_PATH"
   colcon build --symlink-install
   colcon test
   colcon test-result --verbose
   ```

3. From Windows, run `scripts/deploy_rock64.ps1` only when the complete
   build/flash/proof workflow is intended. It flashes through the Rock64
   ST-Link and runs the mandatory UART safety proof before restarting the
   service.
4. Use `/dev/rock64_stm32` for motor communication. Never substitute the
   stock USART3/PD8-PD9 reference endpoint.
5. Follow `docs/OPERATOR_GUIDE.md` for the current raised-track and
   emergency-stop procedure before enabling motor power. The detailed
   `docs/HARDWARE_VALIDATION.md` file is a technical appendix.

PyCharm should be treated as the development and debugging client; it does not
replace the Rock64's ROS environment, the deployment script, or the hardware
safety gate.
