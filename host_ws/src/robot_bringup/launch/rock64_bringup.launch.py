#!/usr/bin/env python3
# pylint: disable=import-error,no-name-in-module
"""Launch the Rock64 control stack through the canonical safety path."""

import os
import sys

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.conditions import IfCondition
from launch.substitutions import (
    EnvironmentVariable,
    LaunchConfiguration,
    PathJoinSubstitution,
)
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

_LAUNCH_DIR = os.path.dirname(__file__)
if _LAUNCH_DIR not in sys.path:
    sys.path.append(_LAUNCH_DIR)

from preflight_check import preflight_or_raise  # noqa: E402


def generate_launch_description() -> LaunchDescription:
    """Build the canonical teleop -> safety -> hardened bridge graph."""
    use_hardware_bridge_arg = DeclareLaunchArgument(
        "use_hardware_bridge",
        default_value="true",
        description="Open the hardened packed-binary STM32 serial bridge",
    )
    use_teleop_arg = DeclareLaunchArgument(
        "use_teleop",
        default_value="true",
        description="Launch the PS5 teleoperation source",
    )
    use_camera_bridge_arg = DeclareLaunchArgument(
        "use_camera_bridge",
        default_value=EnvironmentVariable(
            "USE_CAMERA_BRIDGE",
            default_value="false",
        ),
        description="Launch the ESP32 camera bridge",
    )
    run_motor_bringup_test_arg = DeclareLaunchArgument(
        "run_motor_bringup_test",
        default_value="false",
        description="Publish the low-speed motor bringup sequence",
    )
    serial_port_arg = DeclareLaunchArgument(
        "serial_port",
        default_value=EnvironmentVariable(
            "SERIAL_PORT",
            default_value="/dev/rock64_stm32",
        ),
        description="STM32 packed-binary serial device",
    )
    camera_ip_arg = DeclareLaunchArgument(
        "camera_ip",
        default_value=EnvironmentVariable(
            "CAMERA_IP_STATION",
            default_value="192.168.1.125",
        ),
        description="ESP32 camera address",
    )
    hardware_config_arg = DeclareLaunchArgument(
        "hardware_config",
        default_value=PathJoinSubstitution(
            [
                FindPackageShare("robot_bringup"),
                "config",
                "rock64_hardware.yaml",
            ]
        ),
        description="Shared hardware parameter file",
    )
    safety_config_arg = DeclareLaunchArgument(
        "safety_config",
        default_value=PathJoinSubstitution(
            [
                FindPackageShare("agent_core"),
                "config",
                "safety_gateway.yaml",
            ]
        ),
        description="Safety gateway ROS parameter file",
    )

    safety_gateway = Node(
        package="agent_core",
        executable="safety_gateway",
        name="safety_gateway",
        parameters=[LaunchConfiguration("safety_config")],
        output="screen",
    )
    teleop = Node(
        package="robot_teleop",
        executable="ps5_ros_bridge",
        name="ps5_ros_bridge",
        parameters=[LaunchConfiguration("hardware_config")],
        condition=IfCondition(LaunchConfiguration("use_teleop")),
        output="screen",
    )
    hardened_bridge = Node(
        package="robot_drivers",
        executable="stm32_hardened_bridge",
        name="stm32_hardened_bridge",
        parameters=[
            LaunchConfiguration("hardware_config"),
            {"serial_port": LaunchConfiguration("serial_port")},
        ],
        condition=IfCondition(LaunchConfiguration("use_hardware_bridge")),
        output="screen",
    )
    camera_bridge = Node(
        package="robot_drivers",
        executable="esp32_camera_bridge",
        name="esp32_camera_bridge",
        parameters=[
            LaunchConfiguration("hardware_config"),
            {"camera_ip": LaunchConfiguration("camera_ip")},
            {"stream_port": 81},
        ],
        condition=IfCondition(LaunchConfiguration("use_camera_bridge")),
        output="screen",
    )
    motor_bringup_test = Node(
        package="robot_drivers",
        executable="motor_bringup_test",
        name="motor_bringup_test",
        condition=IfCondition(LaunchConfiguration("run_motor_bringup_test")),
        output="screen",
    )

    return LaunchDescription(
        [
            use_hardware_bridge_arg,
            use_teleop_arg,
            use_camera_bridge_arg,
            run_motor_bringup_test_arg,
            serial_port_arg,
            camera_ip_arg,
            hardware_config_arg,
            safety_config_arg,
            OpaqueFunction(function=preflight_or_raise),
            safety_gateway,
            teleop,
            hardened_bridge,
            camera_bridge,
            motor_bringup_test,
        ]
    )
