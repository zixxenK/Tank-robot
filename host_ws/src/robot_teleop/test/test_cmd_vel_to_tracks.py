"""Tests for the shared Twist-to-track conversion node."""

from geometry_msgs.msg import Twist

from robot_teleop.cmd_vel_to_tracks import CmdVelToTracks


def test_cmd_vel_to_tracks_preserves_an_inside_track_reversal() -> None:
    """A full pivot must reach the explicit left/right track outputs."""
    node = CmdVelToTracks()
    try:
        command = Twist()
        command.linear.x = 0.0
        command.angular.z = -2.0 * 0.8 / 0.194

        node._on_cmd_vel(command)

        assert node._left_pub.last_msg.data == 1.0
        assert node._right_pub.last_msg.data == -1.0
    finally:
        node.destroy_node()


def test_cmd_vel_to_tracks_clamps_a_command_pair_together() -> None:
    """Overspeed Twist input is normalized without changing its ratio."""
    node = CmdVelToTracks()
    try:
        command = Twist()
        command.linear.x = 0.8
        command.angular.z = 8.0

        node._on_cmd_vel(command)

        left = node._left_pub.last_msg.data
        right = node._right_pub.last_msg.data
        assert max(abs(left), abs(right)) == 1.0
        assert right > left
    finally:
        node.destroy_node()
