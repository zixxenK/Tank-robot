#!/usr/bin/env python3
# pylint: disable=import-error,no-name-in-module
"""Launch the Rock64 control stack through the canonical safety path."""

import glob
import os
import sys

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.conditions import IfCondition
from launch.substitutions import (
    EnvironmentVariable,
    LaunchConfiguration,
    PathJoinSubstitution,
)
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

_LAUNCH_DIR = os.path.dirname(__file__)
if _LAUNCH_DIR not in sys.path:
    sys.path.append(_LAUNCH_DIR)

from preflight_check import preflight_or_raise  # noqa: E402


def _default_usb_camera_device() -> str:
    """Resolve the configured camera or the first stable V4L2 index-0 path."""
    configured = os.environ.get("USB_CAMERA_DEVICE", "auto").strip()
    if configured and configured.lower() != "auto":
        return configured
    stable_devices = [
        path
        for path in sorted(glob.glob("/dev/v4l/by-id/*-video-index0"))
        if os.path.exists(path)
    ]
    return stable_devices[0] if stable_devices else "/dev/video0"


def generate_launch_description() -> LaunchDescription:
    """Build the canonical teleop -> safety -> hardened bridge graph."""
    use_hardware_bridge_arg = DeclareLaunchArgument(
        "use_hardware_bridge",
        default_value="true",
        description="Open the hardened packed-binary STM32 serial bridge",
    )
    use_teleop_arg = DeclareLaunchArgument(
        "use_teleop",
        default_value=EnvironmentVariable(
            "USE_TELEOP",
            default_value="true",
        ),
        description="Launch the PS5 teleoperation source",
    )
    use_camera_bridge_arg = DeclareLaunchArgument(
        "use_camera_bridge",
        default_value=EnvironmentVariable(
            "USE_CAMERA_BRIDGE",
            default_value="true",
        ),
        description="Launch the ESP32 camera bridge",
    )
    use_lidar_arg = DeclareLaunchArgument(
        "use_lidar",
        default_value=EnvironmentVariable(
            "USE_LIDAR",
            default_value="false",
        ),
        description="Launch the directly connected STL-50B2 LiDAR",
    )
    use_usb_camera_arg = DeclareLaunchArgument(
        "use_usb_camera",
        default_value=EnvironmentVariable(
            "USE_USB_CAMERA",
            default_value="true",
        ),
        description="Launch the USB webcam bridge",
    )
    run_motor_bringup_test_arg = DeclareLaunchArgument(
        "run_motor_bringup_test",
        default_value="false",
        description="Publish the low-speed motor bringup sequence",
    )
    serial_port_arg = DeclareLaunchArgument(
        "serial_port",
        default_value=EnvironmentVariable(
            "SERIAL_PORT",
            default_value="/dev/rock64_stm32",
        ),
        description="STM32 packed-binary serial device",
    )
    joy_device_arg = DeclareLaunchArgument(
        "joy_device",
        default_value=EnvironmentVariable(
            "PS5_JOY_DEVICE",
            default_value="/dev/input/ps5_controller",
        ),
        description="Required DualSense Linux joystick device",
    )
    camera_ip_arg = DeclareLaunchArgument(
        "camera_ip",
        default_value=EnvironmentVariable(
            "CAMERA_IP_STATION",
            default_value="192.168.1.125",
        ),
        description="ESP32 camera address",
    )
    lidar_serial_port_arg = DeclareLaunchArgument(
        "lidar_serial_port",
        default_value=EnvironmentVariable(
            "LIDAR_SERIAL_PORT",
            default_value="/dev/ttyS2",
        ),
        description="ROCK64 UART2 device for STL-50B2",
    )
    lidar_sync_gpiochip_arg = DeclareLaunchArgument(
        "lidar_sync_gpiochip",
        default_value="/dev/gpiochip2",
        description="GPIO chip for STL-50B2 sync on header pin 12",
    )
    lidar_baudrate_arg = DeclareLaunchArgument(
        "lidar_baudrate",
        default_value=EnvironmentVariable(
            "LIDAR_BAUDRATE", default_value="115200"
        ),
        description="STL-50B2 UART baud rate",
    )
    lidar_use_sync_arg = DeclareLaunchArgument(
        "lidar_use_sync",
        default_value=EnvironmentVariable(
            "LIDAR_USE_SYNC", default_value="true"
        ),
        description="Use GPIO sync edges for LiDAR scan boundaries",
    )
    usb_camera_device_arg = DeclareLaunchArgument(
        "usb_camera_device",
        default_value=_default_usb_camera_device(),
        description="V4L2 device for the USB webcam",
    )
    use_compressed_camera_transport_arg = DeclareLaunchArgument(
        "use_compressed_camera_transport",
        default_value=EnvironmentVariable(
            "USE_COMPRESSED_CAMERA_TRANSPORT",
            default_value="true",
        ),
        description=(
            "Republish camera frames as depth-one JPEG topics for PC/Foxglove "
            "transport"
        ),
    )
    camera_jpeg_quality_arg = DeclareLaunchArgument(
        "camera_jpeg_quality",
        default_value=EnvironmentVariable(
            "CAMERA_JPEG_QUALITY",
            default_value="70",
        ),
        description="JPEG quality for compressed camera transport",
    )
    hardware_config_arg = DeclareLaunchArgument(
        "hardware_config",
        default_value=PathJoinSubstitution(
            [
                FindPackageShare("robot_bringup"),
                "config",
                "rock64_hardware.yaml",
            ]
        ),
        description="Shared hardware parameter file",
    )
    safety_config_arg = DeclareLaunchArgument(
        "safety_config",
        default_value=PathJoinSubstitution(
            [
                FindPackageShare("agent_core"),
                "config",
                "safety_gateway.yaml",
            ]
        ),
        description="Safety gateway ROS parameter file",
    )
    monitor_battery_arg = DeclareLaunchArgument(
        "monitor_battery",
        default_value=EnvironmentVariable(
            "MONITOR_BATTERY",
            default_value="false",
        ),
        description=(
            "Require live STM32 battery telemetry before motion; disabled by "
            "default "
            "for the motor-only firmware image"
        ),
    )
    use_audio_arg = DeclareLaunchArgument(
        "use_audio",
        default_value=EnvironmentVariable(
            "USE_AUDIO",
            default_value="true",
        ),
        description="Launch the buzzer song creator and its ROS audio topics",
    )

    safety_gateway = Node(
        package="agent_core",
        executable="safety_gateway",
        name="safety_gateway",
        parameters=[
            LaunchConfiguration("safety_config"),
            {"monitor_battery": LaunchConfiguration("monitor_battery")},
        ],
        output="screen",
    )
    teleop = Node(
        package="robot_teleop",
        executable="ps5_ros_bridge",
        name="ps5_ros_bridge",
        parameters=[
            LaunchConfiguration("hardware_config"),
            {"joy_device": LaunchConfiguration("joy_device")},
        ],
        condition=IfCondition(LaunchConfiguration("use_teleop")),
        output="screen",
    )
    hardened_bridge = Node(
        package="robot_drivers",
        executable="stm32_hardened_bridge",
        name="stm32_hardened_bridge",
        parameters=[
            LaunchConfiguration("hardware_config"),
            {"serial_port": LaunchConfiguration("serial_port")},
        ],
        condition=IfCondition(LaunchConfiguration("use_hardware_bridge")),
        output="screen",
    )
    buzzer_song_creator = Node(
        package="robot_audio",
        executable="buzzer_song_creator",
        name="buzzer_song_creator",
        parameters=[
            {
                "joy_topic": "/joy",
                "triangle_index": 2,
                "frequency_topic": "/buzzer/frequency",
                "play_sequence_topic": "/buzzer/play_sequence",
                "status_topic": "/buzzer/status",
            }
        ],
        condition=IfCondition(LaunchConfiguration("use_audio")),
        output="screen",
    )
    camera_bridge = Node(
        package="robot_drivers",
        executable="esp32_camera_bridge",
        name="esp32_camera_bridge",
        parameters=[
            LaunchConfiguration("hardware_config"),
            {"camera_ip": LaunchConfiguration("camera_ip")},
            {"stream_port": 81},
        ],
        condition=IfCondition(LaunchConfiguration("use_camera_bridge")),
        output="screen",
    )
    lidar = Node(
        package="robot_drivers",
        executable="stl50b2_lidar",
        name="stl50b2_lidar",
        parameters=[
            {
                "serial_port": LaunchConfiguration("lidar_serial_port"),
                "baudrate": LaunchConfiguration("lidar_baudrate"),
                "use_sync_gpio": LaunchConfiguration("lidar_use_sync"),
                "frame_id": "base_laser",
                "scan_topic": "/scan",
                "sync_gpiochip": LaunchConfiguration("lidar_sync_gpiochip"),
                "sync_line_offset": 3,
                "sync_global_number": 67,
                "allow_sysfs_gpio_fallback": True,
            }
        ],
        condition=IfCondition(LaunchConfiguration("use_lidar")),
        output="screen",
    )
    lidar_tf = Node(
        package="tf2_ros",
        executable="static_transform_publisher",
        name="base_to_laser_tf",
        arguments=[
            "0", "0", "0.18", "0", "0", "0",
            "base_link", "base_laser",
        ],
        condition=IfCondition(LaunchConfiguration("use_lidar")),
        output="screen",
    )
    ultrasonic_tf = Node(
        package="tf2_ros",
        executable="static_transform_publisher",
        name="base_to_ultrasonic_tf",
        arguments=[
            "0.12", "0", "0.12", "0", "0", "0",
            "base_link", "ultrasonic_link",
        ],
        output="screen",
    )
    usb_camera = Node(
        package="robot_drivers",
        executable="usb_webcam_bridge",
        name="usb_webcam_bridge",
        parameters=[{
            "device": LaunchConfiguration("usb_camera_device"),
            "topic": "/camera/usb/image_raw",
            "frame_id": "usb_camera_link",
            "width": 640,
            "height": 480,
            "fps": 15.0,
            "frame_timeout_s": 2.0,
        }],
        condition=IfCondition(LaunchConfiguration("use_usb_camera")),
        output="screen",
    )
    esp32_camera_compressed = Node(
        package="robot_drivers",
        executable="compressed_image_bridge",
        name="esp32_camera_compressed",
        parameters=[
            {
                "input_topic": "/camera/image_raw",
                "output_topic": "/camera/image_raw/compressed",
                "jpeg_quality": LaunchConfiguration("camera_jpeg_quality"),
                "frame_id": "camera_link",
            }
        ],
        condition=IfCondition(
            LaunchConfiguration("use_compressed_camera_transport")
        ),
        output="screen",
    )
    usb_camera_compressed = Node(
        package="robot_drivers",
        executable="compressed_image_bridge",
        name="usb_camera_compressed",
        parameters=[
            {
                "input_topic": "/camera/usb/image_raw",
                "output_topic": "/camera/usb/image_raw/compressed",
                "jpeg_quality": LaunchConfiguration("camera_jpeg_quality"),
                "frame_id": "usb_camera_link",
            }
        ],
        condition=IfCondition(
            LaunchConfiguration("use_compressed_camera_transport")
        ),
        output="screen",
    )
    motor_bringup_test = Node(
        package="robot_drivers",
        executable="motor_bringup_test",
        name="motor_bringup_test",
        condition=IfCondition(LaunchConfiguration("run_motor_bringup_test")),
        output="screen",
    )

    return LaunchDescription(
        [
            use_hardware_bridge_arg,
            use_teleop_arg,
            use_camera_bridge_arg,
            use_lidar_arg,
            use_usb_camera_arg,
            run_motor_bringup_test_arg,
            serial_port_arg,
            joy_device_arg,
            camera_ip_arg,
            lidar_serial_port_arg,
            lidar_sync_gpiochip_arg,
            lidar_baudrate_arg,
            lidar_use_sync_arg,
            usb_camera_device_arg,
            use_compressed_camera_transport_arg,
            camera_jpeg_quality_arg,
            hardware_config_arg,
            safety_config_arg,
            monitor_battery_arg,
            use_audio_arg,
            OpaqueFunction(function=preflight_or_raise),
            safety_gateway,
            teleop,
            hardened_bridge,
            buzzer_song_creator,
            camera_bridge,
            lidar,
            lidar_tf,
            ultrasonic_tf,
            usb_camera,
            esp32_camera_compressed,
            usb_camera_compressed,
            motor_bringup_test,
        ]
    )
