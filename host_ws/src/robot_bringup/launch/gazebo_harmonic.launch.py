#!/usr/bin/env python3
"""Gazebo Harmonic scaffold for Rock64 Ranger.

Starts gz sim with a minimal tank model and bridges key topics between
ROS 2 and Gazebo Transport using ros_gz_bridge.
"""

import os
import shutil

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.actions import ExecuteProcess
from launch.substitutions import LaunchConfiguration
from launch.substitutions import PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    gz_exec = os.environ.get("GZ_SIM_EXEC", "").strip()
    gz_subcommand = os.environ.get("GZ_SIM_SUBCOMMAND", "").strip()

    if not gz_exec:
        if shutil.which("gz"):
            gz_exec = "gz"
            gz_subcommand = "sim"
        elif shutil.which("ign"):
            gz_exec = "ign"
            gz_subcommand = "gazebo"
        else:
            # Gazebo is not installed on this system.  The launch description is
            # still generated so callers can guard it with IfCondition(gui).
            # If gz_sim is actually executed, the process will fail with a clear
            # "command not found" error rather than crashing at parse time.
            gz_exec = "gz"
            gz_subcommand = "sim"

    if not gz_subcommand:
        gz_subcommand = "gazebo" if os.path.basename(gz_exec) == "ign" else "sim"

    world_arg = DeclareLaunchArgument(
        "world",
        default_value=PathJoinSubstitution(
            [FindPackageShare("robot_bringup"), "worlds", "tank_minimal.sdf"]
        ),
        description="Path to the Gazebo Harmonic world file",
    )

    gz_sim = ExecuteProcess(
        cmd=[gz_exec, gz_subcommand, "-r", LaunchConfiguration("world")],
        output="screen",
    )

    ros_gz_bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name="ros_gz_bridge",
        arguments=[
            "/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock",
            "/model/tank_robot/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist",
            "/model/tank_robot/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry",
        ],
        remappings=[
            ("/model/tank_robot/cmd_vel", "/cmd_vel"),
            ("/model/tank_robot/odom", "/odom"),
        ],
        output="screen",
    )

    return LaunchDescription(
        [
            world_arg,
            gz_sim,
            ros_gz_bridge,
        ]
    )
