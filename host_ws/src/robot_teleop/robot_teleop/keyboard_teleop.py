#!/usr/bin/env python3
"""keyboard_teleop.py — Terminal keyboard → /cmd_vel teleop node.

Press WASD / arrow keys to drive the tank; spacebar to stop.
"""

import sys
import tty
import termios
import threading

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist

BINDINGS = {
    "w": ( 1.0,  0.0),
    "s": (-1.0,  0.0),
    "a": ( 0.0,  1.0),
    "d": ( 0.0, -1.0),
    " ": ( 0.0,  0.0),
}

BANNER = """
Rock64 Ranger — Keyboard Teleop
────────────────────────────────
  W / ↑   : Forward
  S / ↓   : Backward
  A / ←   : Turn left
  D / →   : Turn right
  SPACE   : Stop
  Ctrl+C  : Quit
────────────────────────────────
"""


class KeyboardTeleop(Node):
    def __init__(self):
        super().__init__("keyboard_teleop")

        self.declare_parameter("max_linear_speed",  0.5)
        self.declare_parameter("max_angular_speed", 1.0)

        self._max_lin = self.get_parameter("max_linear_speed").value
        self._max_ang = self.get_parameter("max_angular_speed").value

        self._pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self._running = True

        self._key_thread = threading.Thread(target=self._key_loop,
                                            daemon=True)
        self._key_thread.start()
        print(BANNER)

    def _get_key(self) -> str:
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        return ch

    def _key_loop(self):
        while self._running:
            key = self._get_key()
            if key == "\x03":  # Ctrl+C
                self._running = False
                rclpy.shutdown()
                break
            lin, ang = BINDINGS.get(key.lower(), (None, None))
            if lin is not None:
                msg = Twist()
                msg.linear.x  = lin * self._max_lin
                msg.angular.z = ang * self._max_ang
                self._pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = KeyboardTeleop()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
