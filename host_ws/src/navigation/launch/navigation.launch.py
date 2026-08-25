#!/usr/bin/env python3
# Copyright 2026 Tank Robot Team
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
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
