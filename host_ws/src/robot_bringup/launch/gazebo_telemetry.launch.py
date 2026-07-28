#!/usr/bin/env python3
# pyright: reportMissingImports=false, reportMissingModuleSource=false
# pyright: reportMissingTypeStubs=false
# pylint: disable=import-error
"""Launch Gazebo Harmonic with optional RViz telemetry overlays."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    world_arg = DeclareLaunchArgument(
        "world",
        default_value=PathJoinSubstitution(
            [FindPackageShare("robot_bringup"), "worlds", "tank_minimal.sdf"]
        ),
        description="Path to Gazebo world",
    )

    rviz_config_arg = DeclareLaunchArgument(
        "rviz_config",
        default_value=PathJoinSubstitution(
            [
                FindPackageShare("robot_bringup"),
                "rviz",
                "gazebo_telemetry.rviz",
            ]
        ),
        description="RViz config file",
    )

    gui_arg = DeclareLaunchArgument(
        "gui",
        default_value="true",
        description="Start Gazebo GUI / simulation nodes",
    )

    rviz_arg = DeclareLaunchArgument(
        "rviz",
        default_value="true",
        description="Start RViz2 visualization",
    )

    gazebo_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution(
                [
                    FindPackageShare("robot_bringup"),
                    "launch",
                    "gazebo_harmonic.launch.py",
                ]
            )
        ),
        launch_arguments={"world": LaunchConfiguration("world")}.items(),
        condition=IfCondition(LaunchConfiguration("gui")),
    )

    telemetry_markers = Node(
        package="robot_drivers",
        executable="telemetry_markers",
        name="telemetry_markers",
        parameters=[
            {"frame_id": "base_link"},
            {"enable_encoder_telemetry": False},
            {"enable_bridge_alive": False},
        ],
        output="screen",
    )

    rviz = Node(
        package="rviz2",
        executable="rviz2",
        name="rviz2",
        arguments=["-d", LaunchConfiguration("rviz_config")],
        output="screen",
        condition=IfCondition(LaunchConfiguration("rviz")),
    )

    return LaunchDescription(
        [
            world_arg,
            rviz_config_arg,
            gui_arg,
            rviz_arg,
            gazebo_launch,
            telemetry_markers,
            rviz,
        ]
    )