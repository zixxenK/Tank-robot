#!/usr/bin/env python3
"""rock64_bringup.launch.py — Rock64 Ranger system bringup.

Default mode is micro-ROS-first:
- Launch micro-ROS Agent on Rock64
- Launch PS5 teleop bridge
- Launch cmd_vel->tracks mapper for expansion hubs

Legacy Python hardware bridges can be enabled for migration/testing.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.actions import ExecuteProcess
from launch.conditions import IfCondition
from launch.substitutions import (
    LaunchConfiguration,
    EnvironmentVariable,
    PathJoinSubstitution,
)
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    use_micro_ros_arg = DeclareLaunchArgument(
        "use_micro_ros",
        default_value="true",
        description="Launch micro-ROS agent on Rock64",
    )

    use_legacy_bridges_arg = DeclareLaunchArgument(
        "use_legacy_bridges",
        default_value="false",
        description=(
            "Enable legacy STM32/ESP32 Python bridges during migration"
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

    camera_ip_arg = DeclareLaunchArgument(
        "camera_ip",
        default_value=EnvironmentVariable("CAMERA_IP_STATION",
                                          default_value="192.168.1.153"),
        description="IP address of the ESP32 camera node",
    )

    hardware_config_arg = DeclareLaunchArgument(
        "hardware_config",
        default_value=PathJoinSubstitution([
            FindPackageShare("robot_bringup"), "config", "rock64_hardware.yaml"
        ]),
        description="Path to shared bringup parameter file",
    )

    ps5_bridge_node = Node(
        package="robot_teleop",
        executable="ps5_ros_bridge",
        name="ps5_ros_bridge",
        parameters=[LaunchConfiguration("hardware_config")],
        output="screen",
    )

    cmd_vel_to_tracks_node = Node(
        package="robot_teleop",
        executable="cmd_vel_to_tracks",
        name="cmd_vel_to_tracks",
        parameters=[LaunchConfiguration("hardware_config")],
        output="screen",
    )

    micro_ros_agent_process = ExecuteProcess(
        cmd=[
            "micro_ros_agent",
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

    serial_bridge_node = Node(
        package="robot_drivers",
        executable="stm32_serial_bridge",
        name="stm32_serial_bridge",
        condition=IfCondition(LaunchConfiguration("use_legacy_bridges")),
        parameters=[
            LaunchConfiguration("hardware_config"),
            {"serial_port": LaunchConfiguration("serial_port")},
            {"baud_rate": 115200},
        ],
        output="screen",
    )

    camera_bridge_node = Node(
        package="robot_drivers",
        executable="esp32_camera_bridge",
        name="esp32_camera_bridge",
        condition=IfCondition(LaunchConfiguration("use_legacy_bridges")),
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
        micro_ros_transport_arg,
        micro_ros_dev_arg,
        micro_ros_baud_arg,
        serial_port_arg,
        camera_ip_arg,
        hardware_config_arg,
        micro_ros_agent_process,
        ps5_bridge_node,
        cmd_vel_to_tracks_node,
        serial_bridge_node,
        camera_bridge_node,
    ])
