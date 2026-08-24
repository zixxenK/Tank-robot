#!/usr/bin/env python3
"""Autonomous waypoint music trigger for the canonical robot odometry path.

Subscribes to localization (normally ``/stm32/odom``) and automatically triggers
preset audio sequences (such as Sea Shanty 2 upon reaching Port Sarim) when the robot
enters a target coordinate region.
"""

import math
from typing import List, Optional

try:
    import rclpy
    from rclpy.node import Node
    from nav_msgs.msg import Odometry
    from std_msgs.msg import Int32MultiArray, String
except ImportError:
    # Standalone / fallback mocks for testing outside ROS 2 environment
    class _MockMsg:
        pass

    class Odometry(_MockMsg):  # type: ignore[no-redef]
        def __init__(self, x: float = 0.0, y: float = 0.0):
            class _Pos:
                def __init__(self, px, py):
                    self.x = px
                    self.y = py
                    self.z = 0.0
            class _Pose:
                def __init__(self, pos):
                    self.position = pos
            class _PoseWithCovariance:
                def __init__(self, p):
                    self.pose = p
            self.pose = _PoseWithCovariance(_Pose(_Pos(x, y)))

    class Int32MultiArray(_MockMsg):  # type: ignore[no-redef]
        def __init__(self, data=None):
            self.data = data or []

    class String(_MockMsg):  # type: ignore[no-redef]
        def __init__(self, data=""):
            self.data = data

    class Node:  # type: ignore[no-redef]
        def __init__(self, name: str):
            self._name = name

        def get_logger(self):
            node_name = self._name
            class _Logger:
                def info(self, msg):
                    pass
                def warn(self, msg):
                    pass
                def error(self, msg):
                    pass
            return _Logger()

        def create_subscription(self, msg_type, topic, callback, qos_profile):
            return None

        def create_publisher(self, msg_type, topic, qos_profile):
            class _Pub:
                def __init__(self):
                    self.last_msg = None
                def publish(self, msg):
                    self.last_msg = msg
            return _Pub()

        def declare_parameter(self, name, default_val):
            class _Param:
                def __init__(self, val):
                    self.value = val
            return _Param(default_val)

        def get_parameter(self, name):
            class _Param:
                def __init__(self, val):
                    self.value = val
            return _Param(None)

        def destroy_node(self):
            pass


from robot_audio.songs import SEA_SHANTY_2_SEQ


class WaypointMusicTrigger(Node):
    """Trigger buzzer song playback autonomously upon reaching coordinate waypoint."""

    def __init__(self):
        super().__init__('waypoint_music_trigger')

        # Parameter Declarations
        self.declare_parameter('odom_topic', '/stm32/odom')
        self.declare_parameter('sequence_topic', '/buzzer/play_sequence')
        self.declare_parameter('status_topic', '/buzzer/status')
        self.declare_parameter('target_x', 5.0)
        self.declare_parameter('target_y', -2.0)
        self.declare_parameter('trigger_radius', 0.5)
        self.declare_parameter('once_only', True)
        self.declare_parameter('waypoint_name', 'Port Sarim')

        # Retrieve Parameter Values
        odom_topic = self._get_param_val('odom_topic', '/stm32/odom')
        sequence_topic = self._get_param_val('sequence_topic', '/buzzer/play_sequence')
        status_topic = self._get_param_val('status_topic', '/buzzer/status')

        self.target_x = float(self._get_param_val('target_x', 5.0))
        self.target_y = float(self._get_param_val('target_y', -2.0))
        self.trigger_radius = float(self._get_param_val('trigger_radius', 0.5))
        self.once_only = bool(self._get_param_val('once_only', True))
        self.waypoint_name = str(self._get_param_val('waypoint_name', 'Port Sarim'))

        # Subscriptions & Publishers
        self.odom_sub = self.create_subscription(Odometry, odom_topic, self.pose_callback, 10)
        self.sequence_pub = self.create_publisher(Int32MultiArray, sequence_topic, 10)
        self.status_pub = self.create_publisher(String, status_topic, 10)

        # State
        self.has_played: bool = False
        self.song_sequence: List[int] = list(SEA_SHANTY_2_SEQ)

        self.get_logger().info(
            f"Waypoint Music Trigger initialized for '{self.waypoint_name}' at "
            f"({self.target_x}, {self.target_y}), radius {self.trigger_radius}m."
        )

    def _get_param_val(self, name: str, default):
        try:
            param = self.get_parameter(name)
            if param and param.value is not None:
                return param.value
        except Exception:
            pass
        return default

    def pose_callback(self, msg: Odometry):
        """Evaluate position from odometry message and trigger song if inside threshold."""
        if self.has_played and self.once_only:
            return  # Only play once per visit when once_only is True

        current_x = msg.pose.pose.position.x
        current_y = msg.pose.pose.position.y

        # Calculate Euclidean distance to target waypoint
        distance = math.sqrt((current_x - self.target_x) ** 2 + (current_y - self.target_y) ** 2)

        if distance <= self.trigger_radius:
            log_msg = (
                f"Arrived at {self.waypoint_name} waypoint (X: {current_x:.2f}, Y: {current_y:.2f}, "
                f"dist: {distance:.2f}m <= {self.trigger_radius}m). Initiating audio playback."
            )
            self.get_logger().info(log_msg)
            self.publish_status(log_msg)

            self.trigger_playback()

    def trigger_playback(self):
        """Publish the assigned song sequence to the buzzer sequence topic."""
        seq_msg = Int32MultiArray()
        seq_msg.data = list(self.song_sequence)
        self.sequence_pub.publish(seq_msg)
        self.has_played = True

    def reset_trigger(self):
        """Reset the trigger so it can fire again upon next arrival."""
        self.has_played = False
        self.get_logger().info(f"Waypoint trigger for '{self.waypoint_name}' reset.")

    def publish_status(self, text: str):
        """Publish status message string to /buzzer/status."""
        msg = String()
        msg.data = str(text)
        self.status_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = WaypointMusicTrigger()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
