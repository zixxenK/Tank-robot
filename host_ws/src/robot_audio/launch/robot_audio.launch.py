from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            'control_map_path',
            default_value=PathJoinSubstitution([
                FindPackageShare('robot_control'),
                'config',
                'control_map.yaml',
            ]),
            description='Canonical DualSense control-map YAML'
        ),
        DeclareLaunchArgument(
            'joy_topic',
            default_value='/joy',
            description='Topic name for Joy messages'
        ),
        DeclareLaunchArgument(
            'odom_topic',
            default_value='/stm32/odom',
            description='Canonical STM32 odometry topic'
        ),
        DeclareLaunchArgument(
            'target_x',
            default_value='5.0',
            description='Port Sarim waypoint X coordinate'
        ),
        DeclareLaunchArgument(
            'target_y',
            default_value='-2.0',
            description='Port Sarim waypoint Y coordinate'
        ),
        DeclareLaunchArgument(
            'trigger_radius',
            default_value='0.5',
            description='Trigger radius around waypoint (meters)'
        ),
        DeclareLaunchArgument(
            'triangle_index',
            default_value='2',
            description='DualSense Triangle button index in sensor_msgs/Joy'
        ),
        Node(
            package='robot_audio',
            executable='buzzer_song_creator',
            name='buzzer_song_creator',
            output='screen',
            parameters=[{
                'joy_topic': LaunchConfiguration('joy_topic'),
                'frequency_topic': '/buzzer/frequency',
                'play_sequence_topic': '/buzzer/play_sequence',
                'status_topic': '/buzzer/status',
                'command_topic': '/buzzer/command',
                'control_map_path': LaunchConfiguration('control_map_path'),
                'triangle_index': LaunchConfiguration('triangle_index'),
            }]
        ),
        Node(
            package='robot_audio',
            executable='waypoint_music_trigger',
            name='waypoint_music_trigger',
            output='screen',
            parameters=[{
                'odom_topic': LaunchConfiguration('odom_topic'),
                'sequence_topic': '/buzzer/play_sequence',
                'status_topic': '/buzzer/status',
                'target_x': LaunchConfiguration('target_x'),
                'target_y': LaunchConfiguration('target_y'),
                'trigger_radius': LaunchConfiguration('trigger_radius'),
                'waypoint_name': 'Port Sarim',
                'once_only': True,
            }]
        ),
    ])
