#!/usr/bin/env python3
"""rock64_bringup.launch.py — Rock64 Ranger system bringup.

Default mode is legacy-bridge-first to match the active firmware integration:
- Launch PS5 teleop bridge
- Launch STM32/ESP32 Python bridges

micro-ROS mode can be enabled explicitly when the STM32 firmware build
includes the corresponding micro-ROS control path.
"""

import os
import shutil
import sys

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.actions import ExecuteProcess
from launch.actions import LogInfo
from launch.actions import OpaqueFunction
from launch.conditions import IfCondition
from launch.substitutions import (
    LaunchConfiguration,
    EnvironmentVariable,
    PathJoinSubstitution,
    PythonExpression,
)
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

_LAUNCH_DIR = os.path.dirname(__file__)
if _LAUNCH_DIR not in sys.path:
    sys.path.append(_LAUNCH_DIR)

try:
    from preflight_check import preflight_or_raise
except ImportError:
    # If preflight_check is not available, create a no-op version
    def preflight_or_raise(context, *args, **kwargs):
        return []


def generate_launch_description():
    def _bool_expr(*parts):
        return PythonExpression(parts)

    micro_ros_cmd = (
        ["micro_ros_agent"]
        if shutil.which("micro_ros_agent")
        else ["ros2", "run", "micro_ros_agent", "micro_ros_agent"]
    )

    use_micro_ros_arg = DeclareLaunchArgument(
        "use_micro_ros",
        default_value="false",
        description="Launch micro-ROS agent on Rock64",
    )

    use_legacy_bridges_arg = DeclareLaunchArgument(
        "use_legacy_bridges",
        default_value="true",
        description=(
            "Enable legacy STM32/ESP32 Python bridges during migration"
        ),
    )

    allow_mixed_bridges_arg = DeclareLaunchArgument(
        "allow_mixed_bridges",
        default_value="false",
        description=(
            "Allow micro-ROS and legacy bridges together. Disabled by "
            "default to avoid serial transport conflicts."
        ),
    )

    use_binary_bridge_arg = DeclareLaunchArgument(
        "use_binary_bridge",
        default_value="false",
        description=(
            "Use STM32 binary protocol bridge instead of legacy ASCII bridge"
        ),
    )

    use_hardened_bridge_arg = DeclareLaunchArgument(
        "use_hardened_bridge",
        default_value="false",
        description=(
            "Use hardened STM32 binary bridge with CRC validation and reconnect logic"
        ),
    )

    run_motor_bringup_test_arg = DeclareLaunchArgument(
        "run_motor_bringup_test",
        default_value="false",
        description=(
            "Run low-speed /cmd_vel motor direction bring-up sequence"
        ),
    )

    micro_ros_transport_arg = DeclareLaunchArgument(
        "micro_ros_transport",
        default_value=EnvironmentVariable(
            "MICRO_ROS_TRANSPORT", default_value="serial"
        ),
        description="micro-ROS transport: serial|udp4",
    )

    micro_ros_dev_arg = DeclareLaunchArgument(
        "micro_ros_dev",
        default_value=EnvironmentVariable(
            "MICRO_ROS_DEV", default_value="/dev/rock64_stm32"
        ),
        description="micro-ROS serial device for STM32 client",
    )

    micro_ros_baud_arg = DeclareLaunchArgument(
        "micro_ros_baud",
        default_value=EnvironmentVariable(
            "MICRO_ROS_BAUD", default_value="115200"
        ),
        description="micro-ROS serial baud rate",
    )

    serial_port_arg = DeclareLaunchArgument(
        "serial_port",
        default_value=EnvironmentVariable("SERIAL_PORT",
                                          default_value="/dev/rock64_stm32"),
        description="Serial port for STM32 motor controller",
    )

    host_workspace_arg = DeclareLaunchArgument(
        "host_workspace",
        default_value=EnvironmentVariable("HOST_WS_PATH", default_value=""),
        description="Host ROS2 workspace path (informational for migration)",
    )

    camera_ip_arg = DeclareLaunchArgument(
        "camera_ip",
        default_value=EnvironmentVariable("CAMERA_IP_STATION",
                                          default_value="192.168.1.125"),
        description="IP address of the ESP32 camera node",
    )

    use_camera_bridge_arg = DeclareLaunchArgument(
        "use_camera_bridge",
        default_value=EnvironmentVariable(
            "USE_CAMERA_BRIDGE", default_value="false"
        ),
        description="Enable ESP32 camera bridge",
    )

    hardware_config_arg = DeclareLaunchArgument(
        "hardware_config",
        default_value=PathJoinSubstitution([
            FindPackageShare("robot_bringup"), "config", "rock64_hardware.yaml"
        ]),
        description="Path to shared bringup parameter file",
    )

    safety_config_arg = DeclareLaunchArgument(
        "safety_config",
        default_value=PathJoinSubstitution([
            LaunchConfiguration("host_workspace"), "../deployment/safety_config.yaml"
        ]),
        description="Path to safety gateway configuration file",
    )

    ps5_bridge_node = Node(
        package="robot_teleop",
        executable="ps5_ros_bridge",
        name="ps5_ros_bridge",
        parameters=[LaunchConfiguration("hardware_config")],
        output="screen",
    )

    # Safety gateway for agent-driven control with velocity clamping and heartbeat watchdog
    safety_gateway_node = Node(
        package="agent_core",
        executable="safety_gateway",
        name="safety_gateway",
        parameters=[
            {"config_file": LaunchConfiguration("safety_config")},
        ],
        output="screen",
    )

    micro_ros_agent_process = ExecuteProcess(
        cmd=micro_ros_cmd + [
            LaunchConfiguration("micro_ros_transport"),
            "--dev",
            LaunchConfiguration("micro_ros_dev"),
            "--baudrate",
            LaunchConfiguration("micro_ros_baud"),
            "-v4",
        ],
        output="screen",
        condition=IfCondition(LaunchConfiguration("use_micro_ros")),
    )

    motor_bringup_test_node = Node(
        package="robot_drivers",
        executable="motor_bringup_test",
        name="motor_bringup_test",
        condition=IfCondition(_bool_expr(
            "'",
            LaunchConfiguration("use_micro_ros"),
            "' == 'true' and '",
            LaunchConfiguration("run_motor_bringup_test"),
            "' == 'true'",
        )),
        output="screen",
    )

    mixed_mode_warning = LogInfo(
        msg=(
            "[rock64_bringup] Both use_micro_ros and use_legacy_bridges are "
            "true; legacy bridges are suppressed unless "
            "allow_mixed_bridges:=true"
        ),
    )

    preflight_gate = OpaqueFunction(function=preflight_or_raise)

    serial_bridge_node = Node(
        package="robot_drivers",
        executable="stm32_serial_bridge",
        name="stm32_serial_bridge",
        condition=IfCondition(_bool_expr(
            "'",
            LaunchConfiguration("use_legacy_bridges"),
            "' == 'true' and (not ('",
            LaunchConfiguration("use_micro_ros"),
            "' == 'true') or ('",
            LaunchConfiguration("allow_mixed_bridges"),
            "' == 'true')) and not ('",
            LaunchConfiguration("use_binary_bridge"),
            "' == 'true')",
        )),
        parameters=[
            LaunchConfiguration("hardware_config"),
            {"serial_port": LaunchConfiguration("serial_port")},
        ],
        output="screen",
    )

    binary_bridge_node = Node(
        package="robot_drivers",
        executable="stm32_binary_bridge",
        name="stm32_binary_bridge",
        condition=IfCondition(_bool_expr(
            "'",
            LaunchConfiguration("use_legacy_bridges"),
            "' == 'true' and (not ('",
            LaunchConfiguration("use_micro_ros"),
            "' == 'true') or ('",
            LaunchConfiguration("allow_mixed_bridges"),
            "' == 'true')) and ('",
            LaunchConfiguration("use_binary_bridge"),
            "' == 'true')",
        )),
        parameters=[
            LaunchConfiguration("hardware_config"),
            {"serial_port": LaunchConfiguration("serial_port")},
        ],
        output="screen",
    )

    # Hardened bridge with CRC validation and reconnect logic (recommended for production)
    hardened_bridge_node = Node(
        package="robot_drivers",
        executable="stm32_hardened_bridge",
        name="stm32_hardened_bridge",
        condition=IfCondition(_bool_expr(
            "'",
            LaunchConfiguration("use_hardened_bridge"),
            "' == 'true' and (not ('",
            LaunchConfiguration("use_micro_ros"),
            "' == 'true') or ('",
            LaunchConfiguration("allow_mixed_bridges"),
            "' == 'true'))",
        )),
        parameters=[
            LaunchConfiguration("hardware_config"),
            {"serial_port": LaunchConfiguration("serial_port")},
        ],
        output="screen",
    )

    camera_bridge_node = Node(
        package="robot_drivers",
        executable="esp32_camera_bridge",
        name="esp32_camera_bridge",
        condition=IfCondition(_bool_expr(
            "'",
            LaunchConfiguration("use_legacy_bridges"),
            "' == 'true' and (not ('",
            LaunchConfiguration("use_micro_ros"),
            "' == 'true') or ('",
            LaunchConfiguration("allow_mixed_bridges"),
            "' == 'true')) and ('",
            LaunchConfiguration("use_camera_bridge"),
            "' == 'true')",
        )),
        parameters=[
            LaunchConfiguration("hardware_config"),
            {"camera_ip": LaunchConfiguration("camera_ip")},
            {"stream_port": 81},
        ],
        output="screen",
    )

    return LaunchDescription([
        use_micro_ros_arg,
        use_legacy_bridges_arg,
        allow_mixed_bridges_arg,
        use_binary_bridge_arg,
        use_hardened_bridge_arg,
        run_motor_bringup_test_arg,
        micro_ros_transport_arg,
        micro_ros_dev_arg,
        micro_ros_baud_arg,
        serial_port_arg,
        host_workspace_arg,
        camera_ip_arg,
        use_camera_bridge_arg,
        hardware_config_arg,
        safety_config_arg,
        preflight_gate,
        micro_ros_agent_process,
        mixed_mode_warning,
        ps5_bridge_node,
        safety_gateway_node,
        motor_bringup_test_node,
        serial_bridge_node,
        binary_bridge_node,
        hardened_bridge_node,
        camera_bridge_node,
    ])
