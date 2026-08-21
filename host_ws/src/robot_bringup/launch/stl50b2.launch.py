#!/usr/bin/env python3
"""Launch the directly connected STL-50B2 ROCK64 LiDAR driver."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    """Create the STL-50B2 node with the documented ROCK64 pin defaults."""
    lidar = Node(
        package="robot_drivers",
        executable="stl50b2_lidar",
        name="stl50b2_lidar",
        output="screen",
        parameters=[{
            "serial_port": LaunchConfiguration("serial_port"),
            "baudrate": LaunchConfiguration("baudrate"),
            "use_sync_gpio": LaunchConfiguration("use_sync_gpio"),
            "frame_id": "base_laser",
            "scan_topic": "/scan",
            "sync_gpiochip": LaunchConfiguration("sync_gpiochip"),
            "sync_line_offset": LaunchConfiguration("sync_line_offset"),
            "sync_global_number": 67,
            "allow_sysfs_gpio_fallback": True,
        }],
    )
    lidar_tf = Node(
        package="tf2_ros",
        executable="static_transform_publisher",
        name="base_to_laser_tf",
        arguments=[
            "0", "0", "0.18", "0", "0", "0",
            "base_link", "base_laser",
        ],
        output="screen",
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            "serial_port",
            default_value="/dev/ttyS2",
            description="ROCK64 UART2 device (GPIO2_A0/A1, header pins 8/10)",
        ),
        DeclareLaunchArgument(
            "baudrate",
            default_value="115200",
            description="STL-50B2 UART baud rate",
        ),
        DeclareLaunchArgument(
            "use_sync_gpio",
            default_value="true",
            description="Use header pin 12 as a hardware scan boundary",
        ),
        DeclareLaunchArgument(
            "sync_gpiochip",
            default_value="/dev/gpiochip2",
            description="GPIO chip containing GPIO2_A3/header pin 12",
        ),
        DeclareLaunchArgument(
            "sync_line_offset",
            default_value="3",
            description="GPIO2_A3 line offset inside gpiochip2",
        ),
        lidar,
        lidar_tf,
    ])
