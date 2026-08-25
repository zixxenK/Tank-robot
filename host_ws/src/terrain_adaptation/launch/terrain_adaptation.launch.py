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
"""Launch file for terrain adaptation nodes."""

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    """Generate launch description for terrain adaptation package."""
    return LaunchDescription([
        # Terrain classifier node
        Node(
            package='terrain_adaptation',
            executable='terrain_classifier.py',
            name='terrain_classifier',
            parameters=[{
                'imu_topic': '/stm32/imu',
                'terrain_topic': '/terrain/type',
                'window_size': 100,
                'sample_rate': 50.0,
            }],
            output='screen',
        ),

        # Adaptive controller node
        Node(
            package='terrain_adaptation',
            executable='adaptive_controller.py',
            name='adaptive_controller',
            parameters=[{
                'imu_topic': '/stm32/imu',
                # Proposal-only path; the safety gateway owns the final
                # arbitration and requires an agent heartbeat.
                'cmd_vel_input': '/agent/cmd_vel_planned',
                'cmd_vel_output': '/agent/cmd_vel_proposed',
                'terrain_topic': '/terrain/type',
                'window_size': 100,
                'sample_rate': 50.0,
            }],
            output='screen',
        ),
    ])
