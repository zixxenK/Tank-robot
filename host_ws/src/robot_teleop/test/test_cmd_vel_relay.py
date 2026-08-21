from __future__ import annotations

from geometry_msgs.msg import Twist

from robot_teleop.cmd_vel_relay import CmdVelRelay


def test_relay_forwards_finite_commands() -> None:
    relay = CmdVelRelay()
    message = Twist()
    message.linear.x = 0.25
    message.angular.z = -0.4

    relay._on_command(message)

    forwarded = relay._publisher.last_msg
    assert forwarded is not None
    assert forwarded.linear.x == 0.25
    assert forwarded.angular.z == -0.4


def test_relay_stops_on_nonfinite_commands() -> None:
    relay = CmdVelRelay()
    message = Twist()
    message.linear.x = float("nan")
    message.angular.z = 0.4

    relay._on_command(message)

    forwarded = relay._publisher.last_msg
    assert forwarded is not None
    assert forwarded.linear.x == 0.0
    assert forwarded.angular.z == 0.0
