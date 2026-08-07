#!/usr/bin/env python3
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
