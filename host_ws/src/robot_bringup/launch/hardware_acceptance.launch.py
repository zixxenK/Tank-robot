#!/usr/bin/env python3
"""Start the complete Rock64 hardware graph and run its acceptance checks."""

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    TimerAction,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (
    EnvironmentVariable,
    LaunchConfiguration,
    PathJoinSubstitution,
)
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def _bool_parameter(name: str) -> ParameterValue:
    """Return a launch configuration forced to a ROS boolean parameter."""
    return ParameterValue(LaunchConfiguration(name), value_type=bool)


def generate_launch_description() -> LaunchDescription:
    """Launch all normal hardware nodes, then run the ordered test runner."""
    arguments = [
        DeclareLaunchArgument(
            "tracks_raised",
            default_value="false",
            description=(
                "Allow the acceptance runner to move the tracks. Keep false "
                "unless the chassis is securely raised."
            ),
        ),
        DeclareLaunchArgument(
            "use_lidar",
            default_value=EnvironmentVariable(
                "USE_LIDAR",
                default_value="false",
            ),
            description="Launch and require the optional STL-50B2 LiDAR",
        ),
        DeclareLaunchArgument(
            "require_battery",
            default_value=EnvironmentVariable(
                "MONITOR_BATTERY",
                default_value="false",
            ),
            description=(
                "Require finite STM32 battery voltage telemetry. Keep false "
                "until the ADC divider is calibrated on the physical pack."
            ),
        ),
        DeclareLaunchArgument(
            "use_hardware_bridge",
            default_value="true",
            description="Launch the STM32 packed-binary bridge",
        ),
        DeclareLaunchArgument(
            "use_teleop",
            default_value="true",
            description="Launch PS5 DualSense teleoperation",
        ),
        DeclareLaunchArgument(
            "use_camera_bridge",
            default_value="true",
            description="Launch the ESP32 camera bridge",
        ),
        DeclareLaunchArgument(
            "use_usb_camera",
            default_value="true",
            description="Launch the Rock64 USB webcam bridge",
        ),
        DeclareLaunchArgument(
            "use_compressed_camera_transport",
            default_value="true",
            description="Publish bounded JPEG camera transport topics",
        ),
        DeclareLaunchArgument(
            "use_audio",
            default_value="true",
            description="Launch PS5 buzzer/audio controls",
        ),
    ]

    hardware_stack = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution(
                [
                    FindPackageShare("robot_bringup"),
                    "launch",
                    "rock64_bringup.launch.py",
                ]
            )
        ),
        launch_arguments={
            "use_hardware_bridge": LaunchConfiguration("use_hardware_bridge"),
            "use_teleop": LaunchConfiguration("use_teleop"),
            "use_camera_bridge": LaunchConfiguration("use_camera_bridge"),
            "use_usb_camera": LaunchConfiguration("use_usb_camera"),
            "use_compressed_camera_transport": LaunchConfiguration(
                "use_compressed_camera_transport"
            ),
            "use_audio": LaunchConfiguration("use_audio"),
            "use_lidar": LaunchConfiguration("use_lidar"),
        }.items(),
    )

    test_runner = Node(
        package="robot_drivers",
        executable="hardware_test_runner",
        name="hardware_test_runner",
        parameters=[
            {
                "tracks_raised": _bool_parameter("tracks_raised"),
                "require_lidar": _bool_parameter("use_lidar"),
                "require_battery": _bool_parameter("require_battery"),
            }
        ],
        output="screen",
        emulate_tty=True,
    )

    return LaunchDescription(
        arguments
        + [
            hardware_stack,
            TimerAction(period=2.0, actions=[test_runner]),
        ]
    )
