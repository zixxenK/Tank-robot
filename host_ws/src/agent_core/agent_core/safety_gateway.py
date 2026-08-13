#!/usr/bin/env python3
# pylint: disable=import-error,no-name-in-module,no-member
"""Gate all robot velocity commands through one fail-safe policy."""

import math
import time
from typing import Optional, Tuple, TypeAlias

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from rclpy.qos import (
    QoSDurabilityPolicy,
    QoSProfile,
    QoSReliabilityPolicy,
)
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from sensor_msgs.msg import BatteryState
from std_msgs.msg import Bool
from std_srvs.srv import Trigger

Command: TypeAlias = Tuple[float, float]

# reason -> (layer-1 immediate cause, [layer-2 root-cause candidates])
# Keep entries actionable: name the exact topic/command to check, not just
# a restatement of the reason string.
_DIAGNOSIS = {
    "startup": (
        "Gateway just started; no command source selected yet.",
        ["Normal for the first control tick only. If this persists, "
         "no other reason is being reached — check node logs for exceptions."],
    ),
    "operator_estop": (
        "Operator e-stop is latched True on /safety/e_stop.",
        ["Clear it: ros2 topic pub /safety/e_stop std_msgs/Bool '{data: false}'.",
         "Find who last published True: "
         "ros2 topic echo /safety/e_stop --once, then "
         "ros2 topic info /safety/e_stop -v to see the publisher node."],
    ),
    "battery_pending": (
        "No /stm32/battery message yet, but still inside the "
        "battery_startup_grace_period window; commands are allowed "
        "through so bringup does not stall on normal boot timing.",
        ["Informational only. If grace period expires and reason "
         "flips to battery_unavailable, see that entry."],
    ),
    "battery_unavailable": (
        "No /stm32/battery message received since node start and the "
        "startup grace period has expired.",
        ["ros2 node list | grep stm32_hardened_bridge  "
         "(confirm the bridge node is actually running).",
         "ros2 topic echo /stm32/diagnostics --once  "
         "-> check 'Serial Link' status is OK/Connected and "
         "valid_frames is increasing across two calls.",
         "If Serial Link is Connected but valid_frames stays at 0: "
         "firmware is not transmitting — check freertos.c "
         "app_task_entry calls binary_protocol_telemetry_task().",
         "If frames arrive but battery specifically never publishes: "
         "host gate 'tel.battery_voltage > 0' in "
         "stm32_hardened_bridge.py can suppress publish on a bad "
         "read — cross-check firmware/stm32_chassis/Core/Src/adc.c "
         "ContinuousConvMode/DMAContinuousRequests (known single-shot "
         "ADC bug freezes the reading)."],
    ),
    "battery_stale": (
        "A /stm32/battery message was received previously but none "
        "has arrived within battery_timeout seconds.",
        ["ros2 topic hz /stm32/battery  (confirm publish rate has "
         "dropped or stopped).",
         "ros2 topic echo /stm32/diagnostics --once  -> check "
         "'Serial Link' status; a serial disconnect/reconnect cycle "
         "will show as a Disconnected status with rising "
         "reconnect attempts.",
         "Check dmesg for USB CH340 adapter drop: "
         "dmesg | tail -30 | grep -i tty"],
    ),
    "invalid_battery": (
        "The last /stm32/battery message contained a non-finite "
        "voltage (NaN/Inf).",
        ["Check firmware/stm32_chassis/Hiwonder/System/"
         "battery_integration.c Battery_Update() — it should reject "
         "and hold last-good value on out-of-range ADC reads "
         "(5-15V sanity check), not forward NaN.",
         "Call the self-test trigger (ros2 topic pub /stm32/self_test "
         "std_msgs/Empty '{}') and inspect /stm32/self_test_result."],
    ),
    "critical_battery": (
        "Measured battery voltage fell below critical_battery_voltage "
        "and the latch engaged.",
        ["This is a real low-battery condition, not a wiring/telemetry "
         "bug, unless voltage is implausible for the pack in use.",
         "Charge/replace the battery, then call "
         "/safety/reset_battery_latch (std_srvs/Trigger) once voltage "
         "is back above battery_recovery_voltage for "
         "battery_recovery_time seconds."],
    ),
    "battery_latched": (
        "critical_battery already fired once; the latch stays set "
        "until explicitly cleared, even if voltage has since "
        "recovered above the critical threshold.",
        ["Call /safety/reset_battery_latch (std_srvs/Trigger) — it "
         "will report exactly which precondition (stale telemetry, "
         "voltage still below recovery, recovery interval not yet "
         "elapsed) is blocking the reset in its response message."],
    ),
    "command_timeout": (
        "Neither /cmd_vel nor /agent/cmd_vel_proposed has published "
        "within their respective timeouts.",
        ["ros2 topic hz /cmd_vel  (for PS5 teleop: confirm "
         "ps5_ros_bridge is running and the controller is connected — "
         "check its own log for 'PS5 controller not connected').",
         "ros2 node list | grep ps5_ros_bridge"],
    ),
    "agent_heartbeat_stale": (
        "/agent/cmd_vel_proposed is fresh but /agent/heartbeat is "
        "not, so the agent command is being rejected.",
        ["ros2 topic hz /agent/heartbeat",
         "Check the publishing agent node is alive and its heartbeat "
         "timer wasn't blocked by a long-running callback."],
    ),
}


class SafetyGatewayNode(Node):
    """Select, validate, and continuously publish a safe velocity command."""

    def __init__(self) -> None:
        super().__init__("safety_gateway")

        self._declare_parameters()
        self._load_parameters()
        self._validate_parameters()

        now = time.monotonic()
        self._node_start_time = now
        self._last_diagnostic_log_time = 0.0
        self._teleop_command: Optional[Command] = None
        self._teleop_time: Optional[float] = None
        self._agent_command: Optional[Command] = None
        self._agent_time: Optional[float] = None
        self._agent_heartbeat_time: Optional[float] = None

        self._operator_estop = False
        self._battery_latched = False
        self._battery_voltage: Optional[float] = None
        self._battery_time: Optional[float] = None
        self._battery_recovery_since: Optional[float] = None
        self._battery_warning_logged = False

        self._last_output: Command = (0.0, 0.0)
        self._last_publish_time = now
        self._last_reason = "startup"

        command_qos = QoSProfile(
            depth=1,
            reliability=QoSReliabilityPolicy.RELIABLE,
            durability=QoSDurabilityPolicy.VOLATILE,
        )
        self._safe_command_publisher = self.create_publisher(
            Twist,
            self._safe_command_topic,
            command_qos,
        )
        self._diagnostics_publisher = self.create_publisher(
            DiagnosticArray,
            "/safety/diagnostics",
            10,
        )

        self.create_subscription(
            Twist,
            self._teleop_command_topic,
            self._teleop_command_callback,
            10,
        )
        self.create_subscription(
            Twist,
            self._agent_command_topic,
            self._agent_command_callback,
            10,
        )
        self.create_subscription(
            Bool,
            self._estop_topic,
            self._estop_callback,
            10,
        )
        self.create_subscription(
            Bool,
            self._agent_heartbeat_topic,
            self._heartbeat_callback,
            10,
        )

        if self._monitor_battery:
            self.create_subscription(
                BatteryState,
                self._battery_topic,
                self._battery_callback,
                10,
            )

        self.create_service(
            Trigger,
            self._battery_reset_service,
            self._reset_battery_latch,
        )

        self.create_timer(1.0 / self._output_rate_hz, self._control_tick)
        self._publish(0.0, 0.0, "startup", immediate=True)
        self.get_logger().info("Safety gateway initialized")

    def _declare_parameters(self) -> None:
        self.declare_parameter("max_linear_speed", 0.5)
        self.declare_parameter("max_angular_speed", 1.0)
        self.declare_parameter("max_linear_acceleration", 2.0)
        self.declare_parameter("max_angular_acceleration", 4.0)
        self.declare_parameter("teleop_command_timeout", 0.25)
        self.declare_parameter("agent_command_timeout", 0.1)
        self.declare_parameter("agent_heartbeat_timeout", 0.1)
        self.declare_parameter("output_rate_hz", 50.0)
        self.declare_parameter("monitor_battery", True)
        self.declare_parameter("battery_startup_grace_period", 5.0)
        self.declare_parameter("battery_timeout", 1.0)
        self.declare_parameter("minimum_battery_voltage", 10.5)
        self.declare_parameter("critical_battery_voltage", 9.5)
        self.declare_parameter("battery_recovery_voltage", 10.0)
        self.declare_parameter("battery_recovery_time", 2.0)
        self.declare_parameter("teleop_command_topic", "/cmd_vel")
        self.declare_parameter(
            "agent_command_topic",
            "/agent/cmd_vel_proposed",
        )
        self.declare_parameter(
            "safe_command_topic",
            "/ranger/cmd_vel_safe",
        )
        self.declare_parameter("estop_topic", "/safety/e_stop")
        self.declare_parameter(
            "agent_heartbeat_topic",
            "/agent/heartbeat",
        )
        self.declare_parameter("battery_topic", "/stm32/battery")
        self.declare_parameter(
            "battery_reset_service",
            "/safety/reset_battery_latch",
        )

    def _load_parameters(self) -> None:
        def value(name: str):
            return self.get_parameter(name).value

        def safe_float(param_name: str, default: float) -> float:
            val = value(param_name)
            if val is None:
                return default
            try:
                return float(val)
            except (TypeError, ValueError):
                return default

        def safe_str(param_name: str, default: str) -> str:
            val = value(param_name)
            if val is None:
                return default
            return str(val)

        self._max_linear = safe_float("max_linear_speed", 0.5)
        self._max_angular = safe_float("max_angular_speed", 1.0)
        self._max_linear_acceleration = safe_float("max_linear_acceleration", 2.0)
        self._max_angular_acceleration = safe_float(
            "max_angular_acceleration", 4.0
        )
        self._teleop_timeout = safe_float("teleop_command_timeout", 0.25)
        self._agent_timeout = safe_float("agent_command_timeout", 0.1)
        self._heartbeat_timeout = safe_float("agent_heartbeat_timeout", 0.1)
        self._output_rate_hz = safe_float("output_rate_hz", 50.0)
        self._monitor_battery = bool(value("monitor_battery") if value("monitor_battery") is not None else True)
        self._battery_startup_grace = safe_float(
            "battery_startup_grace_period", 5.0
        )
        self._battery_timeout = safe_float("battery_timeout", 1.0)
        self._minimum_battery = safe_float("minimum_battery_voltage", 10.5)
        self._critical_battery = safe_float("critical_battery_voltage", 9.5)
        self._battery_recovery = safe_float("battery_recovery_voltage", 10.0)
        self._battery_recovery_time = safe_float("battery_recovery_time", 2.0)
        self._teleop_command_topic = safe_str("teleop_command_topic", "/cmd_vel")
        self._agent_command_topic = safe_str("agent_command_topic", "/agent/cmd_vel_proposed")
        self._safe_command_topic = safe_str("safe_command_topic", "/ranger/cmd_vel_safe")
        self._estop_topic = safe_str("estop_topic", "/safety/e_stop")
        self._agent_heartbeat_topic = safe_str("agent_heartbeat_topic", "/agent/heartbeat")
        self._battery_topic = safe_str("battery_topic", "/stm32/battery")
        self._battery_reset_service = safe_str("battery_reset_service", "/safety/reset_battery_latch")

    def _validate_parameters(self) -> None:
        positive_values = {
            "max_linear_speed": self._max_linear,
            "max_angular_speed": self._max_angular,
            "max_linear_acceleration": self._max_linear_acceleration,
            "max_angular_acceleration": self._max_angular_acceleration,
            "teleop_command_timeout": self._teleop_timeout,
            "agent_command_timeout": self._agent_timeout,
            "agent_heartbeat_timeout": self._heartbeat_timeout,
            "output_rate_hz": self._output_rate_hz,
            "battery_startup_grace_period": self._battery_startup_grace,
            "battery_timeout": self._battery_timeout,
            "battery_recovery_time": self._battery_recovery_time,
        }
        invalid = [
            name
            for name, item in positive_values.items()
            if not math.isfinite(item) or item <= 0.0
        ]
        if invalid:
            raise ValueError(
                "Safety parameters must be finite and positive: "
                + ", ".join(invalid)
            )

        battery_values = (
            self._critical_battery,
            self._battery_recovery,
            self._minimum_battery,
        )
        if not all(math.isfinite(item) for item in battery_values):
            raise ValueError("Battery thresholds must be finite")
        if not (
            self._critical_battery
            < self._battery_recovery
            <= self._minimum_battery
        ):
            raise ValueError(
                "Battery thresholds must satisfy critical < recovery "
                "<= minimum"
            )

    @staticmethod
    def _command_from_message(message: Twist) -> Optional[Command]:
        linear = float(message.linear.x)
        angular = float(message.angular.z)
        if not (math.isfinite(linear) and math.isfinite(angular)):
            return None
        return linear, angular

    def _teleop_command_callback(self, message: Twist) -> None:
        now = time.monotonic()
        command = self._command_from_message(message)
        self._teleop_command = command if command is not None else (0.0, 0.0)
        self._teleop_time = now
        if command is None:
            self.get_logger().error("Rejected non-finite teleop command")

    def _agent_command_callback(self, message: Twist) -> None:
        now = time.monotonic()
        command = self._command_from_message(message)
        self._agent_command = command if command is not None else (0.0, 0.0)
        self._agent_time = now
        if command is None:
            self.get_logger().error("Rejected non-finite agent command")

    def _heartbeat_callback(self, message: Bool) -> None:
        self._agent_heartbeat_time = time.monotonic() if message.data else None

    def _estop_callback(self, message: Bool) -> None:
        self._operator_estop = bool(message.data)
        if self._operator_estop:
            self._publish(0.0, 0.0, "operator_estop", immediate=True)

    def _battery_callback(self, message: BatteryState) -> None:
        now = time.monotonic()
        # Handle potential None value from message
        voltage_val = message.voltage
        if voltage_val is None:
            self._battery_voltage = None
            self._battery_latched = True
            self._battery_recovery_since = None
            self._publish(0.0, 0.0, "invalid_battery", immediate=True)
            return

        try:
            voltage = float(voltage_val)
        except (TypeError, ValueError):
            self._battery_voltage = None
            self._battery_latched = True
            self._battery_recovery_since = None
            self._publish(0.0, 0.0, "invalid_battery", immediate=True)
            return

        self._battery_time = now

        if not math.isfinite(voltage):
            self._battery_voltage = None
            self._battery_latched = True
            self._battery_recovery_since = None
            self._publish(0.0, 0.0, "invalid_battery", immediate=True)
            return

        self._battery_voltage = voltage
        if voltage < self._critical_battery:
            self._battery_latched = True
            self._battery_recovery_since = None
            self._publish(0.0, 0.0, "critical_battery", immediate=True)
        elif voltage >= self._battery_recovery:
            if self._battery_recovery_since is None:
                self._battery_recovery_since = now
        else:
            self._battery_recovery_since = None

    def _reset_battery_latch(
        self,
        request: Trigger.Request,
        response: Trigger.Response,
    ) -> Trigger.Response:
        del request
        now = time.monotonic()

        if not self._battery_latched:
            response.success = True
            response.message = "Battery latch is already clear"
            return response
        if self._operator_estop:
            response.message = "Operator e-stop is active"
            return response
        if self._battery_time is None or (
            now - self._battery_time > self._battery_timeout
        ):
            response.message = "Battery telemetry is stale"
            return response
        if self._battery_voltage is None or (
            self._battery_voltage < self._battery_recovery
        ):
            response.message = "Battery voltage is below recovery threshold"
            return response
        if self._battery_recovery_since is None or (
            now - self._battery_recovery_since < self._battery_recovery_time
        ):
            response.message = "Battery recovery interval is incomplete"
            return response

        self._battery_latched = False
        response.success = True
        response.message = "Battery latch cleared"
        return response

    def _control_tick(self) -> None:
        now = time.monotonic()
        command, reason = self._select_command(now)
        if command is None:
            self._publish(0.0, 0.0, reason, immediate=True)
            return

        linear, angular = self._limit_command(command, now)
        self._publish(linear, angular, reason, immediate=False)

    def _select_command(
        self,
        now: float,
    ) -> Tuple[Optional[Command], str]:
        if self._operator_estop:
            return None, "operator_estop"
        if self._battery_latched:
            return None, "battery_latched"
        if self._monitor_battery:
            if self._battery_time is None:
                in_grace = (
                    now - self._node_start_time
                    < self._battery_startup_grace
                )
                if in_grace:
                    return None, "battery_pending"
                if not self._battery_warning_logged:
                    self.get_logger().warn(
                        "Battery data unavailable; stopping commands."
                    )
                    self._battery_warning_logged = True
                return None, "battery_unavailable"
            if now - self._battery_time > self._battery_timeout:
                if not self._battery_warning_logged:
                    self.get_logger().warn(
                        "Battery data is stale; stopping commands."
                    )
                    self._battery_warning_logged = True
                return None, "battery_stale"

        if self._teleop_time is not None and (
            now - self._teleop_time <= self._teleop_timeout
        ):
            return self._teleop_command, "teleop"

        if self._agent_time is not None and (
            now - self._agent_time <= self._agent_timeout
        ):
            heartbeat_fresh = (
                self._agent_heartbeat_time is not None
                and now - self._agent_heartbeat_time <= self._heartbeat_timeout
            )
            if heartbeat_fresh:
                return self._agent_command, "agent"
            return None, "agent_heartbeat_stale"

        return None, "command_timeout"

    def _limit_command(self, command: Command, now: float) -> Command:
        linear_limit = self._max_linear
        if (
            self._monitor_battery
            and self._battery_voltage is not None
            and self._battery_voltage < self._minimum_battery
        ):
            battery_range = self._minimum_battery - self._critical_battery
            battery_factor = (
                self._battery_voltage - self._critical_battery
            ) / battery_range
            linear_limit *= max(0.3, min(1.0, battery_factor))

        target_linear = max(-linear_limit, min(linear_limit, command[0]))
        target_angular = max(
            -self._max_angular,
            min(self._max_angular, command[1]),
        )
        delta_time = max(0.0, min(0.1, now - self._last_publish_time))
        return (
            self._approach(
                self._last_output[0],
                target_linear,
                self._max_linear_acceleration * delta_time,
            ),
            self._approach(
                self._last_output[1],
                target_angular,
                self._max_angular_acceleration * delta_time,
            ),
        )

    @staticmethod
    def _approach(current: float, target: float, maximum_step: float) -> float:
        delta = target - current
        if abs(delta) <= maximum_step:
            return target
        return current + math.copysign(maximum_step, delta)

    def _publish(
        self,
        linear: float,
        angular: float,
        reason: str,
        immediate: bool,
    ) -> None:
        if immediate:
            linear = 0.0
            angular = 0.0

        message = Twist()
        message.linear.x = linear
        message.angular.z = angular
        self._safe_command_publisher.publish(message)

        self._last_output = (linear, angular)
        self._last_publish_time = time.monotonic()

        blocked = reason not in ("teleop", "agent")
        reason_changed = reason != self._last_reason
        # Re-announce a blocked reason periodically (not just on the single
        # transition) so it is visible in a log tail taken minutes later,
        # not just buried at boot.
        due_for_reannounce = (
            blocked
            and (self._last_publish_time - self._last_diagnostic_log_time)
            >= 5.0
        )
        if reason_changed or due_for_reannounce:
            layer1, layer2 = _DIAGNOSIS.get(
                reason,
                (f"Unrecognized reason code: {reason}", []),
            )
            self.get_logger().info("Safety state: %s" % reason)
            if blocked:
                self.get_logger().warn(
                    "Stopped: %s | checks: %s"
                    % (layer1, " || ".join(layer2) if layer2 else "n/a")
                )
            self._publish_diagnostics(reason, layer1, layer2, blocked)
            self._last_reason = reason
            self._last_diagnostic_log_time = self._last_publish_time

    def _publish_diagnostics(
        self,
        reason: str,
        layer1: str,
        layer2: list,
        blocked: bool,
    ) -> None:
        diag_array = DiagnosticArray()
        # Handle stamp assignment safely for type checker
        try:
            diag_array.header.stamp = self.get_clock().now().to_msg()
        except AttributeError:
            # Fallback if header structure doesn't match expected type
            pass

        status = DiagnosticStatus()
        status.name = "safety_gateway: Command Selection"
        status.level = (
            DiagnosticStatus.ERROR if blocked else DiagnosticStatus.OK
        )
        status.message = f"{reason}: {layer1}"
        status.values.append(KeyValue(key="reason", value=reason))
        for index, cause in enumerate(layer2):
            status.values.append(
                KeyValue(key=f"check_{index + 1}", value=cause)
            )
        status.values.append(
            KeyValue(
                key="battery_time_known",
                value=str(self._battery_time is not None),
            )
        )
        status.values.append(
            KeyValue(
                key="battery_latched",
                value=str(self._battery_latched),
            )
        )
        status.values.append(
            KeyValue(
                key="operator_estop",
                value=str(self._operator_estop),
            )
        )

        diag_array.status.append(status)
        self._diagnostics_publisher.publish(diag_array)


def main(args=None) -> None:
    """Run the safety gateway node."""
    rclpy.init(args=args)
    node = SafetyGatewayNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
