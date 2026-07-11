#!/usr/bin/env python3
"""rock64_bringup.launch.py — Hardware bringup launch file.

Launches the Arduino serial bridge (STM32 motor control) and the
ESP32 camera bridge into the ROS2 graph.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.substitutions import LaunchConfiguration, EnvironmentVariable
from launch_ros.actions import Node


def generate_launch_description():
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

    serial_bridge_node = Node(
        package="robot_drivers",
        executable="arduino_serial_bridge",
        name="arduino_serial_bridge",
        parameters=[
            {"serial_port": LaunchConfiguration("serial_port")},
            {"baud_rate": 115200},
        ],
        output="screen",
    )

    camera_bridge_node = Node(
        package="robot_drivers",
        executable="esp32_camera_bridge",
        name="esp32_camera_bridge",
        parameters=[
            {"camera_ip": LaunchConfiguration("camera_ip")},
            {"stream_port": 81},
        ],
        output="screen",
    )

    return LaunchDescription([
        serial_port_arg,
        camera_ip_arg,
        serial_bridge_node,
        camera_bridge_node,
    ])
