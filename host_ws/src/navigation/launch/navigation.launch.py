#!/usr/bin/env python3
"""Launch file for navigation nodes."""

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    """Generate launch description for navigation package."""
    return LaunchDescription([
        # Path planner node
        Node(
            package='navigation',
            executable='path_planner.py',
            name='path_planner',
            parameters=[{
                'planner_type': 'astar',
                'map_width': 20,
                'map_height': 20,
                'resolution': 0.1,
                'goal_topic': '/goal_pose',
                'path_topic': '/planned_path',
                # Keep autonomous planning out of the operator /cmd_vel lane.
                # The safety gateway still requires /agent/heartbeat before
                # accepting this proposal.
                'cmd_vel_topic': '/agent/cmd_vel_proposed',
                'odom_topic': '/stm32/odom',
                'diagonal': True,
            }],
            output='screen',
        ),
    ])
