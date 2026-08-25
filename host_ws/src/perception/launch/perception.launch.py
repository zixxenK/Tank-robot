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
"""Launch file for perception nodes."""

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    """Generate launch description for perception package."""
    return LaunchDescription([
        # Object detection node
        Node(
            package='perception',
            executable='object_detector.py',
            name='object_detector',
            parameters=[{
                'input_topic': '/camera/image_raw',
                'output_topic': '/perception/detections',
                'debug_topic': '/perception/debug_image',
                'enable_debug': True,
                'min_confidence': 0.5,
                'max_objects': 10,
            }],
            output='screen',
        ),

        # Obstacle detection node
        Node(
            package='perception',
            executable='obstacle_detector.py',
            name='obstacle_detector',
            parameters=[{
                'input_topic': '/camera/image_raw',
                'output_topic': '/perception/obstacles',
                'avoidance_topic': '/perception/avoidance_vector',
                'enable_debug': True,
                'min_obstacle_area': 1000,
                'max_distance': 3.0,
            }],
            output='screen',
        ),
    ])
