#!/usr/bin/env python3
# pylint: disable=import-error,no-name-in-module,no-member
"""Gate all robot velocity commands through one fail-safe policy."""

import math
import time
from typing import Optional, Tuple

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from rclpy.qos import (
    QoSDurabilityPolicy,
    QoSProfile,
    QoSReliabilityPolicy,
)
from sensor_msgs.msg import BatteryState
from std_msgs.msg import Bool
from std_srvs.srv import Trigger

Command = Tuple[float, float]


class SafetyGatewayNode(Node):
    """Select, validate, and continuously publish a safe velocity command."""

    def __init__(self) -> None:
        super().__init__("safety_gateway")

        self._declare_parameters()
        self._load_parameters()
        self._validate_parameters()

        now = time.monotonic()
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

        self._max_linear = float(value("max_linear_speed"))
        self._max_angular = float(value("max_angular_speed"))
        self._max_linear_acceleration = float(value("max_linear_acceleration"))
        self._max_angular_acceleration = float(
            value("max_angular_acceleration")
        )
        self._teleop_timeout = float(value("teleop_command_timeout"))
        self._agent_timeout = float(value("agent_command_timeout"))
        self._heartbeat_timeout = float(value("agent_heartbeat_timeout"))
        self._output_rate_hz = float(value("output_rate_hz"))
        self._monitor_battery = bool(value("monitor_battery"))
        self._battery_timeout = float(value("battery_timeout"))
        self._minimum_battery = float(value("minimum_battery_voltage"))
        self._critical_battery = float(value("critical_battery_voltage"))
        self._battery_recovery = float(value("battery_recovery_voltage"))
        self._battery_recovery_time = float(value("battery_recovery_time"))
        self._teleop_command_topic = str(value("teleop_command_topic"))
        self._agent_command_topic = str(value("agent_command_topic"))
        self._safe_command_topic = str(value("safe_command_topic"))
        self._estop_topic = str(value("estop_topic"))
        self._agent_heartbeat_topic = str(value("agent_heartbeat_topic"))
        self._battery_topic = str(value("battery_topic"))
        self._battery_reset_service = str(value("battery_reset_service"))

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
        voltage = float(message.voltage)
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
                return None, "battery_unavailable"
            if now - self._battery_time > self._battery_timeout:
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
        if reason != self._last_reason:
            self.get_logger().info("Safety state: %s" % reason)
            self._last_reason = reason


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
