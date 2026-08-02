"""Safety tests for LM Studio movement argument validation."""

import math

import pytest

from agent_core.lmstudio_nodes import TeleopChatNode


def test_missing_movement_field_is_rejected() -> None:
    """Incomplete model tool calls fail closed."""
    with pytest.raises(ValueError, match="angular_rps"):
        TeleopChatNode._validated_command(
            {"linear_mps": 0.1, "duration_seconds": 0.5}
        )


def test_non_finite_movement_is_rejected() -> None:
    """Non-finite values cannot pass into the gateway command topic."""
    with pytest.raises(ValueError, match="finite"):
        TeleopChatNode._validated_command(
            {
                "linear_mps": math.nan,
                "angular_rps": 0.0,
                "duration_seconds": 0.5,
            }
        )


def test_movement_is_clamped_to_bridge_limits() -> None:
    """Model values are bounded before the gateway applies its own limits."""
    result = TeleopChatNode._validated_command(
        {
            "linear_mps": 3.0,
            "angular_rps": -4.0,
            "duration_seconds": 20.0,
        }
    )
    assert result is not None
    twist, duration = result
    assert twist.linear.x == 0.2
    assert twist.angular.z == -0.5
    assert duration == 1.0
