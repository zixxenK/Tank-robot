#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool, Header
from sensor_msgs.msg import BatteryState, Imu
import time
import yaml
import os

class SafetyGatewayNode(Node):
    def __init__(self):
        super().__init__('safety_gateway')
        
        # Try to load safety config file
        config_file = self.declare_parameter('config_file', '').value
        if config_file and os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    config = yaml.safe_load(f)
                    safety_config = config.get('safety_gateway', {})

                    # Load from config file with fallbacks
                    default_linear = safety_config.get('kinematic_limits', {}).get('max_linear_speed', 0.5)
                    default_angular = safety_config.get('kinematic_limits', {}).get('max_angular_speed', 1.0)
                    default_timeout = safety_config.get('heartbeat_timeout_ms', 500) / 1000.0  # Convert ms to seconds
                    default_hard_stop = safety_config.get('enable_hard_stop', True)
                    default_min_battery = safety_config.get('min_battery_voltage', 10.5)
                    default_critical_battery = safety_config.get('critical_battery_voltage', 9.5)
                    default_max_accel = safety_config.get('max_acceleration', 2.0)
                    default_telemetry_monitoring = safety_config.get('enable_telemetry_monitoring', True)
                    
                    self.get_logger().info(f"Loaded safety config from {config_file}")
            except Exception as e:
                self.get_logger().warn(f"Failed to load config file {config_file}: {e}, using defaults")
                default_linear = 0.5
                default_angular = 1.0
                default_timeout = 0.5
                default_hard_stop = True
                default_min_battery = 10.5
                default_critical_battery = 9.5
                default_max_accel = 2.0
                default_telemetry_monitoring = True
        else:
            # Use hardcoded defaults if no config file
            default_linear = 0.5
            default_angular = 1.0
            default_timeout = 0.5
            default_hard_stop = True
            default_min_battery = 10.5
            default_critical_battery = 9.5
            default_max_accel = 2.0
            default_telemetry_monitoring = True
            if config_file:
                self.get_logger().warn(f"Config file {config_file} not found, using defaults")
        
        # Declare parameters for safety bounds and watchdog timeout
        self.declare_parameter('max_linear_speed', default_linear)
        self.declare_parameter('max_angular_speed', default_angular)
        self.declare_parameter('heartbeat_timeout', default_timeout)
        self.declare_parameter('enable_hard_stop', default_hard_stop)
        self.declare_parameter('min_battery_voltage', default_min_battery)  # Below this, reduce max speed
        self.declare_parameter('critical_battery_voltage', default_critical_battery)  # Below this, hard stop
        self.declare_parameter('max_acceleration', default_max_accel)  # m/s^2
        self.declare_parameter('enable_telemetry_monitoring', default_telemetry_monitoring)

        self._max_linear = float(self.get_parameter("max_linear_speed").value)  # type: ignore[arg-type]
        self._max_angular = float(self.get_parameter("max_angular_speed").value)  # type: ignore[arg-type]
        self._heartbeat_timeout = float(self.get_parameter("heartbeat_timeout").value)  # type: ignore[arg-type]
        self._enable_hard_stop = bool(self.get_parameter("enable_hard_stop").value)  # type: ignore[arg-type]
        self._min_battery_voltage = float(self.get_parameter("min_battery_voltage").value)  # type: ignore[arg-type]
        self._critical_battery_voltage = float(self.get_parameter("critical_battery_voltage").value)  # type: ignore[arg-type]
        self._max_acceleration = float(self.get_parameter("max_acceleration").value)  # type: ignore[arg-type]
        self._enable_telemetry_monitoring = bool(self.get_parameter("enable_telemetry_monitoring").value)  # type: ignore[arg-type]

        self._last_heartbeat_time = time.time()
        self._e_stop_active = False

        # Telemetry monitoring state
        self._battery_voltage = 12.0  # Default to healthy
        self._last_battery_time = 0.0
        self._current_accel = 0.0
        self._last_cmd_vel = Twist()
        self._last_cmd_time = time.time()

        # Subscriptions
        self.create_subscription(Twist, '/agent/cmd_vel_proposed', self.proposed_cmd_callback, 10)
        self.create_subscription(Bool, '/safety/e_stop', self.e_stop_callback, 10)
        self.create_subscription(Bool, '/agent/heartbeat', self.heartbeat_callback, 10)

        # Telemetry subscriptions for dynamic safety monitoring
        if self._enable_telemetry_monitoring:
            self.create_subscription(BatteryState, '/stm32/battery', self.battery_callback, 10)
            self.create_subscription(Imu, '/stm32/imu', self.imu_callback, 10)

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

    def battery_callback(self, msg: BatteryState):
        """Monitor battery voltage and dynamically adjust speed limits."""
        self._battery_voltage = msg.voltage
        self._last_battery_time = time.time()

        # Check for critical battery level
        if self._battery_voltage < self._critical_battery_voltage:
            self.get_logger().error(f"CRITICAL BATTERY: {self._battery_voltage:.2f}V - Initiating hard stop")
            self._e_stop_active = True
            self.publish_zero_velocity()
        elif self._battery_voltage < self._min_battery_voltage:
            self.get_logger().warn(f"LOW BATTERY: {self._battery_voltage:.2f}V - Reducing max speed")

    def imu_callback(self, msg: Imu):
        """Monitor acceleration for dynamic safety limits."""
        # Calculate total acceleration magnitude
        accel_x = msg.linear_acceleration.x  # type: ignore[attr-defined]
        accel_y = msg.linear_acceleration.y  # type: ignore[attr-defined]
        accel_z = msg.linear_acceleration.z  # type: ignore[attr-defined]
        self._current_accel = (accel_x**2 + accel_y**2 + accel_z**2)**0.5

        # Warn if acceleration exceeds safe limits
        if self._current_accel > self._max_acceleration:
            self.get_logger().warn(f"HIGH ACCELERATION: {self._current_accel:.2f} m/s²")

    def proposed_cmd_callback(self, msg: Twist):
        if self._e_stop_active:
            return  # Drop commands entirely during e-stop

        # Check heartbeat freshness
        if (time.time() - self._last_heartbeat_time) > self._heartbeat_timeout:
            self.get_logger().error("Heartbeat lost! Blocking agent command.")
            self.publish_zero_velocity()
            return

        # Dynamic speed limit based on battery voltage
        if self._enable_telemetry_monitoring and (time.time() - self._last_battery_time) < 1.0:
            if self._battery_voltage < self._min_battery_voltage:
                # Reduce max speed proportionally to battery voltage
                battery_factor = (self._battery_voltage - self._critical_battery_voltage) / (self._min_battery_voltage - self._critical_battery_voltage)
                dynamic_max_linear = self._max_linear * max(0.3, battery_factor)  # Never below 30%
            else:
                dynamic_max_linear = self._max_linear
        else:
            dynamic_max_linear = self._max_linear

        # Acceleration limiting
        proposed_linear = msg.linear.x
        if self._enable_telemetry_monitoring:
            dt = time.time() - self._last_cmd_time
            if dt > 0 and dt < 0.1:  # Only limit if reasonable time delta
                accel_limit = self._max_acceleration * dt
                delta_linear = proposed_linear - self._last_cmd_vel.linear.x
                if abs(delta_linear) > accel_limit:
                    # Clamp acceleration
                    limited_delta = accel_limit if delta_linear > 0 else -accel_limit
                    proposed_linear = self._last_cmd_vel.linear.x + limited_delta

        # Clamp linear and angular velocities to dynamic limits (Parameter Nudging / Safety Gating)
        safe_msg = Twist()
        safe_msg.linear.x = max(-dynamic_max_linear, min(dynamic_max_linear, proposed_linear))
        safe_msg.angular.z = max(-self._max_angular, min(self._max_angular, msg.angular.z))

        # Store for next acceleration check
        self._last_cmd_vel = safe_msg
        self._last_cmd_time = time.time()

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