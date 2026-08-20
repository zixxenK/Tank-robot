#!/usr/bin/env python3
"""PC-side read-only Foxglove and SLAM launch profile.

The Rock64 acquisition graph remains a separate process.  This launch file
contains only nodes that belong on the PC ROS 2 environment: TF completion,
Foxglove transport, and optional SLAM/Nav2 workloads.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (
    LaunchConfiguration,
    PathJoinSubstitution,
    PythonExpression,
)
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def _condition_for_mode(mode: str):
    """Return a launch condition for the requested SLAM mode."""
    return IfCondition(
        PythonExpression([
            "'",
            LaunchConfiguration("slam_mode"),
            "' == '",
            mode,
            "' and '",
            LaunchConfiguration("use_slam"),
            "' == 'true'",
        ])
    )


def _include(package: str, launch_file: str, arguments: dict, condition=None):
    """Include an installed launch file with optional condition."""
    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare(package),
                "launch",
                launch_file,
            ])
        ),
        launch_arguments=arguments.items(),
        condition=condition,
    )


def generate_launch_description() -> LaunchDescription:
    """Generate the PC-only read-only visualization graph."""
    use_foxglove = DeclareLaunchArgument("use_foxglove", default_value="true")
    foxglove_port = DeclareLaunchArgument("foxglove_port", default_value="8765")
    foxglove_address = DeclareLaunchArgument(
        "foxglove_address",
        default_value="127.0.0.1",
        description="Bind Foxglove Bridge locally unless LAN viewing is explicitly needed",
    )
    use_odom_tf = DeclareLaunchArgument("use_odom_tf", default_value="true")
    use_slam = DeclareLaunchArgument("use_slam", default_value="true")
    slam_mode = DeclareLaunchArgument(
        "slam_mode",
        default_value="mapping",
        description="mapping or localization",
    )
    slam_params_file = DeclareLaunchArgument(
        "slam_params_file",
        default_value=PathJoinSubstitution([
            FindPackageShare("robot_bringup"),
            "config",
            "slam_toolbox_pc.yaml",
        ]),
    )
    map_file_name = DeclareLaunchArgument(
        "map_file_name",
        default_value="",
        description="Saved map basename for localization mode",
    )
    use_nav2 = DeclareLaunchArgument(
        "use_nav2",
        default_value="false",
        description=(
            "Disabled by default: Nav2 must not be allowed to command the "
            "robot until its safety-gateway integration is commissioned"
        ),
    )

    odom_tf = Node(
        package="robot_drivers",
        executable="odom_tf_broadcaster",
        name="odom_tf_broadcaster",
        parameters=[
            {
                "odom_topic": "/stm32/odom",
                "odom_frame": "odom",
                "base_frame": "base_link",
            }
        ],
        condition=IfCondition(LaunchConfiguration("use_odom_tf")),
        output="screen",
    )
    foxglove = Node(
        package="foxglove_bridge",
        executable="foxglove_bridge",
        name="foxglove_bridge",
        parameters=[
            {
                "port": LaunchConfiguration("foxglove_port"),
                "address": LaunchConfiguration("foxglove_address"),
                "send_buffer_limit": 10000000,
                # Do not expose Foxglove's clientPublish or service/parameter
                # mutation capabilities in the commissioning dashboard.
                "capabilities": ["connectionGraph", "assets"],
            }
        ],
        condition=IfCondition(LaunchConfiguration("use_foxglove")),
        output="screen",
    )
    slam_mapping = _include(
        "slam_toolbox",
        "online_async_launch.py",
        {
            "use_sim_time": "false",
            "slam_params_file": LaunchConfiguration("slam_params_file"),
        },
        _condition_for_mode("mapping"),
    )
    slam_localization = _include(
        "slam_toolbox",
        "localization_launch.py",
        {
            "use_sim_time": "false",
            "slam_params_file": LaunchConfiguration("slam_params_file"),
            "map_file_name": LaunchConfiguration("map_file_name"),
        },
        _condition_for_mode("localization"),
    )
    nav2 = _include(
        "nav2_bringup",
        "navigation_launch.py",
        {
            "use_sim_time": "false",
            "autostart": "true",
        },
        IfCondition(LaunchConfiguration("use_nav2")),
    )

    return LaunchDescription([
        use_foxglove,
        foxglove_port,
        foxglove_address,
        use_odom_tf,
        use_slam,
        slam_mode,
        slam_params_file,
        map_file_name,
        use_nav2,
        odom_tf,
        foxglove,
        slam_mapping,
        slam_localization,
        nav2,
    ])
