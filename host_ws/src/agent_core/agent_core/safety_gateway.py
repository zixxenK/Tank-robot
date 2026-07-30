#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool, Header
import time

class SafetyGatewayNode(Node):
    def __init__(self):
        super().__init__('safety_gateway')
        
        # Declare parameters for safety bounds and watchdog timeout
        self.declare_parameter('max_linear_speed', 0.5)
        self.declare_parameter('max_angular_speed', 1.0)
        self.declare_parameter('heartbeat_timeout', 0.5)
        self.declare_parameter('enable_hard_stop', True)

        self._max_linear = float(self.get_parameter("max_linear_speed").value)  # type: ignore[arg-type]
        self._max_angular = float(self.get_parameter("max_angular_speed").value)  # type: ignore[arg-type]
        self._heartbeat_timeout = float(self.get_parameter("heartbeat_timeout").value)  # type: ignore[arg-type]
        self._enable_hard_stop = bool(self.get_parameter("enable_hard_stop").value)  # type: ignore[arg-type]

        self._last_heartbeat_time = time.time()
        self._e_stop_active = False

        # Subscriptions
        self.create_subscription(Twist, '/agent/cmd_vel_proposed', self.proposed_cmd_callback, 10)
        self.create_subscription(Bool, '/safety/e_stop', self.e_stop_callback, 10)
        self.create_subscription(Bool, '/agent/heartbeat', self.heartbeat_callback, 10)

        # Publisher to hardware/STM32 bridge
        self._safe_cmd_pub = self.create_publisher(Twist, '/ranger/cmd_vel_safe', 10)

        # 50Hz safety watchdog timer loop
        self.create_timer(0.02, self.safety_watchdog_loop)
        self.get_logger().info("Safety Gateway initialized and actively monitoring command stream.")

    def e_stop_callback(self, msg: Bool):
        self._e_stop_active = msg.data
        if self._e_stop_active:
            self.get_logger().warn("E-STOP TRIGGERED! Halting all agent motion.")
            self.publish_zero_velocity()

    def heartbeat_callback(self, msg: Bool):
        if msg.data:
            self._last_heartbeat_time = time.time()

    def proposed_cmd_callback(self, msg: Twist):
        if self._e_stop_active:
            return  # Drop commands entirely during e-stop

        # Check heartbeat freshness
        if (time.time() - self._last_heartbeat_time) > self._heartbeat_timeout:
            self.get_logger().error("Heartbeat lost! Blocking agent command.")
            self.publish_zero_velocity()
            return

        # Clamp linear and angular velocities to hard limits (Parameter Nudging / Safety Gating)
        safe_msg = Twist()
        safe_msg.linear.x = max(-self._max_linear, min(self._max_linear, msg.linear.x))
        safe_msg.angular.z = max(-self._max_angular, min(self._max_angular, msg.angular.z))

        # Pass the validated command down to the base controller
        self._safe_cmd_pub.publish(safe_msg)

    def safety_watchdog_loop(self):
        # Periodic check for silent watchdog failure
        if (time.time() - self._last_heartbeat_time) > self._heartbeat_timeout and not self._e_stop_active:
            self.publish_zero_velocity()

    def publish_zero_velocity(self):
        zero_msg = Twist()
        self._safe_cmd_pub.publish(zero_msg)

def main(args=None):
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
