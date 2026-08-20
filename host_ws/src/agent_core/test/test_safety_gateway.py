"""Unit tests for the safety gateway policy without a ROS runtime."""

from unittest.mock import patch

from geometry_msgs.msg import Twist
from std_srvs.srv import Trigger

from agent_core.safety_gateway import SafetyGatewayNode


def _gateway() -> SafetyGatewayNode:
    gateway = object.__new__(SafetyGatewayNode)
    gateway._operator_estop = False
    gateway._battery_latched = False
    gateway._monitor_battery = False
    gateway._battery_time = None
    gateway._battery_timeout = 1.0
    gateway._teleop_command = None
    gateway._teleop_time = None
    gateway._teleop_timeout = 0.25
    gateway._agent_command = None
    gateway._agent_time = None
    gateway._agent_timeout = 0.1
    gateway._agent_heartbeat_time = None
    gateway._heartbeat_timeout = 0.1
    gateway._node_start_time = 0.0
    gateway._battery_startup_grace = 5.0
    gateway._battery_warning_logged = False
    return gateway


def test_nonfinite_command_is_rejected() -> None:
    message = Twist()
    message.linear.x = float("nan")

    assert SafetyGatewayNode._command_from_message(message) is None


def test_fresh_teleop_has_priority_without_agent_heartbeat() -> None:
    gateway = _gateway()
    gateway._teleop_command = (0.2, -0.1)
    gateway._teleop_time = 10.0
    gateway._agent_command = (0.5, 0.5)
    gateway._agent_time = 10.0

    command, reason = gateway._select_command(10.05)

    assert command == (0.2, -0.1)
    assert reason == "teleop"


def test_agent_requires_fresh_true_heartbeat() -> None:
    gateway = _gateway()
    gateway._agent_command = (0.3, 0.2)
    gateway._agent_time = 10.0

    command, reason = gateway._select_command(10.05)
    assert command is None
    assert reason == "agent_heartbeat_stale"

    gateway._agent_heartbeat_time = 10.0
    command, reason = gateway._select_command(10.05)
    assert command == (0.3, 0.2)
    assert reason == "agent"


def test_stale_teleop_command_stops_the_output() -> None:
    gateway = _gateway()
    gateway._teleop_command = (0.2, 0.0)
    gateway._teleop_time = 10.0

    command, reason = gateway._select_command(10.251)

    assert command is None
    assert reason == "command_timeout"


def test_stale_agent_heartbeat_stops_an_agent_command() -> None:
    gateway = _gateway()
    gateway._agent_command = (0.2, 0.0)
    gateway._agent_time = 10.0
    gateway._agent_heartbeat_time = 9.9

    command, reason = gateway._select_command(10.051)

    assert command is None
    assert reason == "agent_heartbeat_stale"


def test_estop_and_battery_latch_override_commands() -> None:
    gateway = _gateway()
    gateway._teleop_command = (0.2, 0.0)
    gateway._teleop_time = 10.0

    gateway._operator_estop = True
    assert gateway._select_command(10.05) == (None, "operator_estop")

    gateway._operator_estop = False
    gateway._battery_latched = True
    assert gateway._select_command(10.05) == (None, "battery_latched")


def test_missing_battery_blocks_commands_after_startup_grace() -> None:
    gateway = _gateway()
    gateway._monitor_battery = True
    gateway._teleop_command = (0.2, 0.0)
    gateway._teleop_time = 10.0

    command, reason = gateway._select_command(10.05)
    assert command is None
    assert reason == "battery_unavailable"


def test_missing_battery_is_pending_during_startup_grace() -> None:
    gateway = _gateway()
    gateway._monitor_battery = True
    gateway._node_start_time = 10.0

    command, reason = gateway._select_command(10.05)
    assert command is None
    assert reason == "battery_pending"


def test_stale_battery_blocks_commands() -> None:
    gateway = _gateway()
    gateway._monitor_battery = True
    gateway._battery_time = 8.0
    gateway._teleop_command = (0.2, 0.0)
    gateway._teleop_time = 10.0

    command, reason = gateway._select_command(10.05)
    assert command is None
    assert reason == "battery_stale"


def test_battery_latch_reset_requires_stable_recovery() -> None:
    gateway = _gateway()
    gateway._battery_latched = True
    gateway._battery_time = 10.0
    gateway._battery_voltage = 10.2
    gateway._battery_recovery = 10.0
    gateway._battery_recovery_since = 7.0
    gateway._battery_recovery_time = 2.0

    response = Trigger.Response()
    with patch("agent_core.safety_gateway.time.monotonic", return_value=10.0):
        result = gateway._reset_battery_latch(Trigger.Request(), response)

    assert result.success is True
    assert gateway._battery_latched is False


def test_approach_respects_slew_limit() -> None:
    assert SafetyGatewayNode._approach(0.0, 1.0, 0.2) == 0.2
    assert SafetyGatewayNode._approach(0.5, 0.4, 0.2) == 0.4
