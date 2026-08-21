#!/usr/bin/env python3
"""Launch the complete Rock64 hardware and autonomous ROS 2 graph.

This is a complete-stack entry point, not a companion to
``rock64_bringup.launch.py``. The included canonical bringup owns the STM32
serial bridge, safety gateway, sensor acquisition, and optional operator
inputs; this file adds perception, planning, and terrain adaptation on top.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (
    LaunchConfiguration,
    PathJoinSubstitution,
    PythonExpression,
)
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description() -> LaunchDescription:
    """Generate a complete hardware-to-autonomy stack."""
    use_hardware_bridge_arg = DeclareLaunchArgument(
        "use_hardware_bridge",
        default_value="true",
        description="Open the production STM32 serial bridge",
    )
    use_teleop_arg = DeclareLaunchArgument(
        "use_teleop",
        default_value="false",
        description="Launch the PS5 operator input alongside autonomy",
    )
    serial_port_arg = DeclareLaunchArgument(
        "serial_port",
        default_value="/dev/rock64_stm32",
        description="Production STM32 serial device",
    )
    monitor_battery_arg = DeclareLaunchArgument(
        "monitor_battery",
        default_value="false",
        description="Require validated STM32 battery telemetry before motion",
    )
    use_audio_arg = DeclareLaunchArgument(
        "use_audio",
        default_value="false",
        description="Launch the PS5-triggered buzzer/song node",
    )
    use_perception_arg = DeclareLaunchArgument(
        "use_perception",
        default_value="true",
        description="Launch object and obstacle perception nodes",
    )
    use_navigation_arg = DeclareLaunchArgument(
        "use_navigation",
        default_value="true",
        description="Launch the odometry-gated path planner",
    )
    use_terrain_adaptation_arg = DeclareLaunchArgument(
        "use_terrain_adaptation",
        default_value="true",
        description="Launch IMU terrain classification and command adaptation",
    )
    use_camera_arg = DeclareLaunchArgument(
        "use_camera",
        default_value="false",
        description="Launch the ESP32 camera and feed perception images",
    )
    camera_ip_arg = DeclareLaunchArgument(
        "camera_ip",
        default_value="192.168.1.125",
        description="ESP32 camera address",
    )

    # The canonical hardware graph owns the only safety gateway and the only
    # STM32 bridge. Keeping those nodes in one include prevents the old
    # autonomous launch from silently publishing commands with no hardware
    # consumer, or from creating two competing safety owners.
    hardware_stack = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare("robot_bringup"),
                "launch",
                "rock64_bringup.launch.py",
            ])
        ),
        launch_arguments={
            "use_hardware_bridge": LaunchConfiguration("use_hardware_bridge"),
            "use_teleop": LaunchConfiguration("use_teleop"),
            "serial_port": LaunchConfiguration("serial_port"),
            "monitor_battery": LaunchConfiguration("monitor_battery"),
            "use_audio": LaunchConfiguration("use_audio"),
            "use_camera_bridge": LaunchConfiguration("use_camera"),
            "use_compressed_camera_transport": LaunchConfiguration("use_camera"),
            "camera_ip": LaunchConfiguration("camera_ip"),
            "use_usb_camera": "false",
            "use_lidar": "false",
        }.items(),
    )

    object_detector = Node(
        package="perception",
        executable="object_detector.py",
        name="object_detector",
        parameters=[{
            "input_topic": "/camera/image_raw",
            "output_topic": "/perception/detections",
            "debug_topic": "/perception/debug_image",
            "enable_debug": True,
        }],
        condition=IfCondition(LaunchConfiguration("use_perception")),
        output="screen",
    )
    obstacle_detector = Node(
        package="perception",
        executable="obstacle_detector.py",
        name="obstacle_detector",
        parameters=[{
            "input_topic": "/camera/image_raw",
            "output_topic": "/perception/obstacles",
            "avoidance_topic": "/perception/avoidance_vector",
            "enable_debug": True,
        }],
        condition=IfCondition(LaunchConfiguration("use_perception")),
        output="screen",
    )
    path_planner = Node(
        package="navigation",
        executable="path_planner.py",
        name="path_planner",
        parameters=[{
            "planner_type": "astar",
            "map_width": 20,
            "map_height": 20,
            "resolution": 0.1,
            "goal_topic": "/goal_pose",
            "path_topic": "/planned_path",
            # Terrain adaptation consumes this intermediate command and emits
            # the final /cmd_vel input for the safety gateway.
            "cmd_vel_topic": "/cmd_vel_planned",
            "odom_topic": "/stm32/odom",
            "diagonal": True,
        }],
        condition=IfCondition(LaunchConfiguration("use_navigation")),
        output="screen",
    )
    terrain_classifier = Node(
        package="terrain_adaptation",
        executable="terrain_classifier.py",
        name="terrain_classifier",
        parameters=[{
            "imu_topic": "/stm32/imu",
            "terrain_topic": "/terrain/type",
            "window_size": 100,
            "sample_rate": 50.0,
        }],
        condition=IfCondition(LaunchConfiguration("use_terrain_adaptation")),
        output="screen",
    )
    adaptive_controller = Node(
        package="terrain_adaptation",
        executable="adaptive_controller.py",
        name="adaptive_controller",
        parameters=[{
            "imu_topic": "/stm32/imu",
            "cmd_vel_input": "/cmd_vel_planned",
            # The safety gateway owns /cmd_vel and applies its timeout, clamp,
            # e-stop, and optional battery gate before the bridge.
            "cmd_vel_output": "/cmd_vel",
            "terrain_topic": "/terrain/type",
            "window_size": 100,
            "sample_rate": 50.0,
        }],
        condition=IfCondition(LaunchConfiguration("use_terrain_adaptation")),
        output="screen",
    )
    direct_command_relay = Node(
        package="robot_teleop",
        executable="cmd_vel_relay",
        name="autonomous_cmd_vel_relay",
        parameters=[{
            "input_topic": "/cmd_vel_planned",
            "output_topic": "/cmd_vel",
        }],
        # If terrain adaptation is disabled, keep the planner connected to
        # the safety gateway instead of leaving /cmd_vel_planned unconsumed.
        condition=IfCondition(PythonExpression([
            "'",
            LaunchConfiguration("use_navigation"),
            "' == 'true' and '",
            LaunchConfiguration("use_terrain_adaptation"),
            "' == 'false'",
        ])),
        output="screen",
    )

    return LaunchDescription([
        use_hardware_bridge_arg,
        use_teleop_arg,
        serial_port_arg,
        monitor_battery_arg,
        use_audio_arg,
        use_perception_arg,
        use_navigation_arg,
        use_terrain_adaptation_arg,
        use_camera_arg,
        camera_ip_arg,
        hardware_stack,
        object_detector,
        obstacle_detector,
        path_planner,
        terrain_classifier,
        adaptive_controller,
        direct_command_relay,
    ])
