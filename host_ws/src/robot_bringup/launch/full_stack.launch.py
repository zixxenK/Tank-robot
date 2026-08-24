#!/usr/bin/env python3
"""Launch the hardware graph plus an explicitly opt-in autonomy profile.

This is a complete-stack entry point, not a companion to
``rock64_bringup.launch.py``. The included canonical bringup owns the STM32
serial bridge, safety gateway, sensor acquisition, and optional operator
inputs; this file adds future-facing perception, planning, and terrain
adaptation on top. Autonomous nodes publish proposals only and remain
disabled by default until an agent supervisor and heartbeat are commissioned.
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
    control_map_arg = DeclareLaunchArgument(
        "control_map",
        default_value=PathJoinSubstitution([
            FindPackageShare("robot_control"),
            "config",
            "control_map.yaml",
        ]),
        description="Canonical PS5 control mapping and tracked-drive geometry",
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
        default_value="false",
        description="Opt in to future read-only perception nodes",
    )
    use_navigation_arg = DeclareLaunchArgument(
        "use_navigation",
        default_value="false",
        description="Opt in to future proposal-only path planning",
    )
    use_terrain_adaptation_arg = DeclareLaunchArgument(
        "use_terrain_adaptation",
        default_value="false",
        description="Opt in to future proposal-only terrain adaptation",
    )
    use_camera_arg = DeclareLaunchArgument(
        "use_camera",
        default_value="true",
        description="Launch the ESP32 and USB camera acquisition paths",
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
            "control_map": LaunchConfiguration("control_map"),
            "monitor_battery": LaunchConfiguration("monitor_battery"),
            "use_audio": LaunchConfiguration("use_audio"),
            "use_camera_bridge": LaunchConfiguration("use_camera"),
            "use_compressed_camera_transport": LaunchConfiguration("use_camera"),
            "camera_ip": LaunchConfiguration("camera_ip"),
            "use_usb_camera": LaunchConfiguration("use_camera"),
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
            # Terrain adaptation consumes this intermediate proposal and
            # emits the final agent proposal. Never publish autonomy to the
            # PS5/maintenance /cmd_vel lane.
            "cmd_vel_topic": "/agent/cmd_vel_planned",
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
            "cmd_vel_input": "/agent/cmd_vel_planned",
            # The safety gateway owns the final agent proposal boundary and
            # applies its heartbeat, timeout, clamp, e-stop, and battery gate.
            "cmd_vel_output": "/agent/cmd_vel_proposed",
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
            "input_topic": "/agent/cmd_vel_planned",
            "output_topic": "/agent/cmd_vel_proposed",
        }],
        # If terrain adaptation is disabled, keep the planner connected to
        # the agent proposal boundary instead of leaving it unconsumed.
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
        control_map_arg,
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
