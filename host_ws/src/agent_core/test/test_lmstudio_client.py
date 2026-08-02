"""Unit tests for response parsing that do not require a live model."""

import json

from agent_core.lmstudio_client import LMStudioClient


def test_extracts_native_tool_call() -> None:
    """LM Studio native tool-call dictionaries are accepted."""
    output = [
        {
            "type": "tool_call",
            "tool": "move_robot",
            "arguments": {"linear_mps": 0.1},
        }
    ]
    assert LMStudioClient._extract_tool_arguments(
        output,
        "move_robot",
    ) == {"linear_mps": 0.1}


def test_extracts_openai_function_call() -> None:
    """OpenAI-compatible JSON argument strings are accepted."""
    arguments = {"linear_mps": 0.0, "duration_seconds": 0.0}
    output = [
        {
            "type": "function_call",
            "name": "move_robot",
            "arguments": json.dumps(arguments),
        }
    ]
    assert LMStudioClient._extract_tool_arguments(
        output,
        "move_robot",
    ) == arguments


def test_ignores_nonmatching_tool() -> None:
    """Calls to tools outside the requested allowlist are ignored."""
    output = [
        {
            "type": "tool_call",
            "tool": "other_tool",
            "arguments": {},
        }
    ]
    assert LMStudioClient._extract_tool_arguments(
        output,
        "move_robot",
    ) is None
