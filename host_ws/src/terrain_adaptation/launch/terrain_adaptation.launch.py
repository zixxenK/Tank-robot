#!/usr/bin/env python3
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
                'cmd_vel_input': '/cmd_vel',
                'cmd_vel_output': '/cmd_vel_adapted',
                'terrain_topic': '/terrain/type',
                'window_size': 100,
                'sample_rate': 50.0,
            }],
            output='screen',
        ),
    ])
