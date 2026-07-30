#!/usr/bin/env python3
import serial
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import threading

class UARTBridge(Node):
    def __init__(self):
        super().__init__('uart_bridge')
        self.subscription = self.create_subscription(Twist, 'cmd_vel', self.cmd_vel_callback, 10)
        self.serial_port = '/dev/ttyACM0'
        self.baudrate = 115200
        try:
            self.ser = serial.Serial(self.serial_port, self.baudrate, timeout=1)
            self.get_logger().info(f'Connected to {self.serial_port}')
        except serial.SerialException as e:
            self.get_logger().error(f'Serial error: {e}')
            self.ser = None
        self.serial_thread = threading.Thread(target=self.read_serial, daemon=True)
        self.serial_thread.start()
    
    def cmd_vel_callback(self, msg):
        if self.ser is None:
            return
        linear_speed = msg.linear.x * 1000.0
        angular_speed = msg.angular.z
        left_speed = linear_speed - angular_speed * 150.0
        right_speed = linear_speed + angular_speed * 150.0
        left_direction = 1 if left_speed >= 0 else 0
        left_pwm = int(abs(left_speed) / 500.0 * 255)
        left_pwm = max(0, min(255, left_pwm))
        right_direction = 1 if right_speed >= 0 else 0
        right_pwm = int(abs(right_speed) / 500.0 * 255)
        right_pwm = max(0, min(255, right_pwm))
        cmd_left = f'<0,{left_direction},{left_pwm}>\n'
        cmd_right = f'<1,{right_direction},{right_pwm}>\n'
        self.ser.write(cmd_left.encode())
        self.ser.write(cmd_right.encode())
    
    def read_serial(self):
        while rclpy.ok():
            if self.ser and self.ser.in_waiting > 0:
                try:
                    data = self.ser.readline().decode().strip()
                    if data:
                        self.get_logger().info(f'UART: {data}')
                except Exception as e:
                    self.get_logger().error(f'Error: {e}')
    
    def stop_motors(self):
        if self.ser:
            self.ser.write(b'STOP\n')

def main(args=None):
    rclpy.init(args=args)
    bridge = UARTBridge()
    try:
        rclpy.spin(bridge)
    except KeyboardInterrupt:
        pass
    finally:
        bridge.stop_motors()
        bridge.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()