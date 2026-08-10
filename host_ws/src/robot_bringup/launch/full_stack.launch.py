#!/usr/bin/env python3
"""Launch file for full autonomous stack including perception, navigation, and terrain adaptation."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    """Generate launch description for full autonomous stack."""
    
    # Launch arguments
    use_perception_arg = DeclareLaunchArgument(
        'use_perception',
        default_value='true',
        description='Launch perception nodes (object detection, obstacle detection)'
    )
    use_navigation_arg = DeclareLaunchArgument(
        'use_navigation',
        default_value='true',
        description='Launch navigation nodes (path planning)'
    )
    use_terrain_adaptation_arg = DeclareLaunchArgument(
        'use_terrain_adaptation',
        default_value='true',
        description='Launch terrain adaptation nodes'
    )
    use_camera_arg = DeclareLaunchArgument(
        'use_camera',
        default_value='false',
        description='Launch camera bridge for perception'
    )
    
    # Perception nodes
    object_detector = Node(
        package='perception',
        executable='object_detector.py',
        name='object_detector',
        parameters=[{
            'input_topic': '/camera/image_raw',
            'output_topic': '/perception/detections',
            'debug_topic': '/perception/debug_image',
            'enable_debug': True,
        }],
        condition=IfCondition(LaunchConfiguration('use_perception')),
        output='screen',
    )
    
    obstacle_detector = Node(
        package='perception',
        executable='obstacle_detector.py',
        name='obstacle_detector',
        parameters=[{
            'input_topic': '/camera/image_raw',
            'output_topic': '/perception/obstacles',
            'avoidance_topic': '/perception/avoidance_vector',
            'enable_debug': True,
        }],
        condition=IfCondition(LaunchConfiguration('use_perception')),
        output='screen',
    )
    
    # Navigation node
    path_planner = Node(
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
            'cmd_vel_topic': '/cmd_vel_planned',  # Changed to avoid conflict
            'diagonal': True,
        }],
        condition=IfCondition(LaunchConfiguration('use_navigation')),
        output='screen',
    )
    
    # Terrain adaptation nodes
    terrain_classifier = Node(
        package='terrain_adaptation',
        executable='terrain_classifier.py',
        name='terrain_classifier',
        parameters=[{
            'imu_topic': '/stm32/imu',
            'terrain_topic': '/terrain/type',
            'window_size': 100,
            'sample_rate': 50.0,
        }],
        condition=IfCondition(LaunchConfiguration('use_terrain_adaptation')),
        output='screen',
    )
    
    adaptive_controller = Node(
        package='terrain_adaptation',
        executable='adaptive_controller.py',
        name='adaptive_controller',
        parameters=[{
            'imu_topic': '/stm32/imu',
            'cmd_vel_input': '/cmd_vel_planned',  # Input from path planner
            'cmd_vel_output': '/cmd_vel',  # Output to safety gateway
            'terrain_topic': '/terrain/type',
            'window_size': 100,
            'sample_rate': 50.0,
        }],
        condition=IfCondition(LaunchConfiguration('use_terrain_adaptation')),
        output='screen',
    )
    
    # Camera bridge (from robot_drivers)
    camera_bridge = Node(
        package='robot_drivers',
        executable='esp32_camera_bridge',
        name='esp32_camera_bridge',
        parameters=[{
            'camera_ip': '192.168.1.125',
            'stream_port': 81,
        }],
        condition=IfCondition(LaunchConfiguration('use_camera')),
        output='screen',
    )
    
    return LaunchDescription([
        use_perception_arg,
        use_navigation_arg,
        use_terrain_adaptation_arg,
        use_camera_arg,
        object_detector,
        obstacle_detector,
        path_planner,
        terrain_classifier,
        adaptive_controller,
        camera_bridge,
    ])
