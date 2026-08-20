#!/usr/bin/env python3
"""Compatibility alias for the PC-side dashboard launch.

Despite the historical filename, this launch file never starts Rock64
hardware, cameras, SLAM, or Nav2.  Use ``pc_dashboard.launch.py`` for the
explicit name; this alias prevents older operator commands from silently
moving heavy workloads back onto the Rock64.
"""

from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description() -> LaunchDescription:
    """Include the canonical PC-only dashboard launch."""
    return LaunchDescription([
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                PathJoinSubstitution([
                    FindPackageShare("robot_bringup"),
                    "launch",
                    "pc_dashboard.launch.py",
                ])
            )
        )
    ])
