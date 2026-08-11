"""ROS 2 nodes that expose LM Studio through constrained robot workflows."""

import json
import math
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional

import rclpy
from diagnostic_msgs.msg import DiagnosticArray
from geometry_msgs.msg import Twist
from rclpy.node import Node
from std_msgs.msg import Bool, String
import threading

from agent_core.lmstudio_client import LMStudioClient, LMStudioError

_MOVE_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "move_robot",
    "description": (
        "Propose a short tank robot movement. Use zero speeds to stop."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "linear_mps": {"type": "number", "minimum": -0.2, "maximum": 0.2},
            "angular_rps": {"type": "number", "minimum": -0.5, "maximum": 0.5},
            "duration_seconds": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
            },
        },
        "required": ["linear_mps", "angular_rps", "duration_seconds"],
        "additionalProperties": False,
    },
}


class _LMStudioNode(Node):
    """Load common LM Studio parameters for bridge nodes."""

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.declare_parameter("base_url", "http://192.168.56.1:1234")
        self.declare_parameter("model", "llama-3.2-1b-instruct")
        self.declare_parameter("request_timeout", 60.0)
        
        base_url = self.get_parameter("base_url").value
        model = self.get_parameter("model").value
        timeout = self.get_parameter("request_timeout").value
        
        self._client = LMStudioClient(
            str(base_url) if base_url is not None else "http://192.168.56.1:1234",
            str(model) if model is not None else "llama-3.2-1b-instruct",
            float(timeout) if timeout is not None else 60.0,
        )

    def _publish_error(self, error: Exception) -> None:
        self.get_logger().error(str(error))


class CodegenProposalNode(_LMStudioNode):
    """Write requested code suggestions to review files without executing."""

    def __init__(self) -> None:
        super().__init__("lmstudio_codegen_proposals")
        self.declare_parameter(
            "proposal_directory",
            "/tmp/tank_robot_codegen_proposals",
        )
        self._proposal_directory = Path(
            str(self.get_parameter("proposal_directory").value)
        )
        self._result_publisher = self.create_publisher(
            String,
            "/agent/codegen/result",
            10,
        )
        self.create_subscription(
            String,
            "/agent/codegen/request",
            self._request_callback,
            10,
        )

    def _request_callback(self, message: String) -> None:
        try:
            proposal = self._client.chat(
                "You propose Tank-robot ROS 2 code changes for human review. "
                "Never claim to execute, deploy, flash, or move hardware. "
                "Include affected paths, tests, and safety implications.",
                message.data,
            )
            self._proposal_directory.mkdir(parents=True, exist_ok=True)
            slug = re.sub(r"[^a-z0-9]+", "-", message.data.lower()).strip("-")
            filename = f"{int(time.time())}-{slug[:48] or 'proposal'}.md"
            path = self._proposal_directory / filename
            path.write_text(proposal + "\n", encoding="utf-8")
            result = String()
            result.data = str(path)
            self._result_publisher.publish(result)
        except (LMStudioError, OSError) as error:
            self._publish_error(error)


class DiagnosticsAssistantNode(_LMStudioNode):
    """Explain the latest ROS diagnostics without taking corrective action."""

    def __init__(self) -> None:
        super().__init__("lmstudio_diagnostics_assistant")
        self._latest_diagnostics = "No diagnostics received"
        self._result_publisher = self.create_publisher(
            String,
            "/agent/diagnostics/result",
            10,
        )
        self.create_subscription(
            DiagnosticArray,
            "/diagnostics",
            self._diagnostics_callback,
            10,
        )
        self.create_subscription(
            String,
            "/agent/diagnostics/request",
            self._request_callback,
            10,
        )

    def _diagnostics_callback(self, message: DiagnosticArray) -> None:
        statuses = []
        for status in message.status:
            statuses.append(
                {
                    "name": status.name,
                    "level": int(status.level),
                    "message": status.message,
                    "values": {item.key: item.value for item in status.values},
                }
            )
        self._latest_diagnostics = json.dumps(statuses)[:12000]

    def _request_callback(self, message: String) -> None:
        try:
            report = self._client.chat(
                "Analyze Tank-robot diagnostics. Be concise, distinguish "
                "evidence from hypotheses, and suggest read-only checks "
                "first. "
                "Do not issue motor, deployment, or flashing commands.",
                f"Question: {message.data}\nDiagnostics: "
                f"{self._latest_diagnostics}",
            )
            result = String()
            result.data = report
            self._result_publisher.publish(result)
        except LMStudioError as error:
            self._publish_error(error)


class TeleopChatNode(_LMStudioNode):
    """Convert explicit chat or voice transcripts to brief gated commands."""

    def __init__(self) -> None:
        super().__init__("lmstudio_teleop_chat")
        self.declare_parameter("publish_rate_hz", 20.0)
        self._command: Optional[Twist] = None
        self._command_deadline = 0.0
        self._llm_thread: Optional[threading.Thread] = None
        self._llm_lock = threading.Lock()
        self._command_publisher = self.create_publisher(
            Twist,
            "/agent/cmd_vel_proposed",
            10,
        )
        self._heartbeat_publisher = self.create_publisher(
            Bool,
            "/agent/heartbeat",
            10,
        )
        self._status_publisher = self.create_publisher(
            String,
            "/agent/teleop/status",
            10,
        )
        self.create_subscription(
            String,
            "/agent/chat/request",
            self._request_callback,
            10,
        )
        self.create_subscription(
            String,
            "/agent/voice/transcript",
            self._request_callback,
            10,
        )
        rate_param = self.get_parameter("publish_rate_hz").value
        rate = float(rate_param) if rate_param is not None else 20.0
        if not math.isfinite(rate) or rate < 11.0:
            raise ValueError("publish_rate_hz must be finite and at least 11")
        self.create_timer(1.0 / rate, self._publish_tick)

    def _request_callback(self, message: String) -> None:
        # Spawn background thread for LLM call to prevent blocking timer callbacks
        if self._llm_thread is not None and self._llm_thread.is_alive():
            self._publish_status("busy: previous LLM request still processing")
            return

        self._llm_thread = threading.Thread(
            target=self._llm_inference_thread,
            args=(message.data,),
            daemon=True
        )
        self._llm_thread.start()

    def _llm_inference_thread(self, user_input: str) -> None:
        """Background thread for LLM inference to prevent blocking heartbeat timer."""
        if user_input.strip().lower() in {"stop", "halt", "cancel"}:
            with self._llm_lock:
                self._stop("operator stop")
            return

        try:
            arguments = self._client.call_tool(user_input, _MOVE_TOOL)
            command = self._validated_command(arguments)
            if command is None:
                with self._llm_lock:
                    self._stop("request did not produce a valid movement")
                return
            twist, duration = command
            with self._llm_lock:
                self._command = twist
                self._command_deadline = time.monotonic() + duration
                self._publish_status(
                    f"accepted for {duration:.2f}s; safety gateway remains active"
                )
        except (LMStudioError, ValueError, TypeError) as error:
            with self._llm_lock:
                self._stop(f"rejected: {error}")

    @staticmethod
    def _validated_command(
        arguments: Optional[Dict[str, Any]],
    ) -> Optional[tuple]:
        if arguments is None:
            return None
        try:
            linear = float(arguments["linear_mps"])
            angular = float(arguments["angular_rps"])
            duration = float(arguments["duration_seconds"])
        except KeyError as error:
            raise ValueError(
                f"movement is missing {error.args[0]}"
            ) from error
        values = (linear, angular, duration)
        if not all(math.isfinite(item) for item in values):
            raise ValueError("movement values must be finite")
        twist = Twist()
        twist.linear.x = max(-0.2, min(0.2, linear))
        twist.angular.z = max(-0.5, min(0.5, angular))
        return twist, max(0.0, min(1.0, duration))

    def _publish_tick(self) -> None:
        with self._llm_lock:
            if self._command is None:
                return
            if time.monotonic() >= self._command_deadline:
                self._stop("command duration elapsed")
                return
            heartbeat = Bool()
            heartbeat.data = True
            self._heartbeat_publisher.publish(heartbeat)
            self._command_publisher.publish(self._command)

    def _stop(self, reason: str) -> None:
        self._command = None
        self._command_deadline = 0.0
        self._command_publisher.publish(Twist())
        heartbeat = Bool()
        heartbeat.data = False
        self._heartbeat_publisher.publish(heartbeat)
        self._publish_status(reason)

    def _publish_status(self, text: str) -> None:
        message = String()
        message.data = text
        self._status_publisher.publish(message)


def _spin(node_type) -> None:
    rclpy.init()
    node = node_type()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


def codegen_main() -> None:
    """Run the proposal-only code generation node."""
    _spin(CodegenProposalNode)


def diagnostics_main() -> None:
    """Run the read-only diagnostics assistant node."""
    _spin(DiagnosticsAssistantNode)


def teleop_main() -> None:
    """Run the safety-gated chat and voice teleoperation node."""
    _spin(TeleopChatNode)
