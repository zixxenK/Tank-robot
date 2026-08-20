"""Unit tests for WaypointMusicTrigger node and coordinate-based audio triggering."""

import pytest
from robot_audio.waypoint_music_trigger import WaypointMusicTrigger, Odometry
from robot_audio.songs import SEA_SHANTY_2_SEQ


@pytest.fixture
def waypoint_trigger():
    try:
        import rclpy
        if not rclpy.ok():
            rclpy.init()
    except Exception:
        pass
    node = WaypointMusicTrigger()
    yield node
    try:
        node.destroy_node()
        import rclpy
        if rclpy.ok():
            rclpy.shutdown()
    except Exception:
        pass


def make_odom(x: float, y: float) -> Odometry:
    """Create test Odometry message with position coordinates."""
    return Odometry(x=x, y=y)


def test_waypoint_trigger_within_radius(waypoint_trigger: WaypointMusicTrigger):
    """Odometry within target waypoint radius triggers song playback."""
    last_pub = {}
    class MockPub:
        def publish(self, msg):
            last_pub['msg'] = msg
    waypoint_trigger.sequence_pub = MockPub()

    # Target is (5.0, -2.0) with radius 0.5
    odom_outside = make_odom(0.0, 0.0)
    waypoint_trigger.pose_callback(odom_outside)
    assert not waypoint_trigger.has_played
    assert 'msg' not in last_pub

    # Move inside trigger radius: (5.1, -2.1) -> dist approx 0.141m <= 0.5m
    odom_inside = make_odom(5.1, -2.1)
    waypoint_trigger.pose_callback(odom_inside)
    assert waypoint_trigger.has_played
    assert 'msg' in last_pub
    assert last_pub['msg'].data == list(SEA_SHANTY_2_SEQ)


def test_waypoint_once_only_behavior(waypoint_trigger: WaypointMusicTrigger):
    """Waypoint trigger fires only once when once_only is enabled."""
    publish_count = 0
    class MockPub:
        def publish(self, msg):
            nonlocal publish_count
            publish_count += 1
    waypoint_trigger.sequence_pub = MockPub()

    # First arrival
    waypoint_trigger.pose_callback(make_odom(5.0, -2.0))
    assert publish_count == 1
    assert waypoint_trigger.has_played

    # Subsequent updates inside the waypoint area
    waypoint_trigger.pose_callback(make_odom(5.05, -2.02))
    assert publish_count == 1


def test_waypoint_trigger_reset(waypoint_trigger: WaypointMusicTrigger):
    """Resetting the trigger allows firing on subsequent arrival."""
    publish_count = 0
    class MockPub:
        def publish(self, msg):
            nonlocal publish_count
            publish_count += 1
    waypoint_trigger.sequence_pub = MockPub()

    # First arrival
    waypoint_trigger.pose_callback(make_odom(5.0, -2.0))
    assert publish_count == 1

    # Reset trigger
    waypoint_trigger.reset_trigger()
    assert not waypoint_trigger.has_played

    # Second arrival
    waypoint_trigger.pose_callback(make_odom(5.0, -2.0))
    assert publish_count == 2
