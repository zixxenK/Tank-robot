#!/usr/bin/env python3
"""keyboard_teleop.py — Terminal keyboard → /cmd_vel teleop node.

Press WASD / arrow keys to drive the tank; spacebar to stop.
"""

import sys
import threading
import math
from pathlib import Path

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from robot_control.control_map import (
    ControlMap,
    default_control_map,
    load_control_map,
)

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

        self.declare_parameter("control_map_path", "")
        # Retained for compatibility with older launch commands. A non-positive
        # value means the canonical tracked-drive map owns the limit.
        self.declare_parameter("max_linear_speed",  -1.0)
        self.declare_parameter("max_angular_speed", -1.0)

        control_map_path = str(
            self.get_parameter("control_map_path").value or ""
        )
        self._control_map = self._load_control_map(control_map_path)
        canonical_linear = self._control_map.max_track_speed_mps
        canonical_angular = (
            2.0 * canonical_linear / self._control_map.track_width_m
        )
        configured_linear = self._positive_float_parameter("max_linear_speed")
        configured_angular = self._positive_float_parameter("max_angular_speed")
        self._max_lin = (
            configured_linear if configured_linear is not None else canonical_linear
        )
        # Steering is the same tracked-drive quantity as PS5/L2 steering. Keep
        # the ceiling derived from the shared geometry even when an old launch
        # file still provides max_angular_speed.
        self._max_ang = canonical_angular
        if configured_linear is not None and not math.isclose(
            configured_linear, canonical_linear, rel_tol=1e-6, abs_tol=1e-6
        ):
            self.get_logger().warn(
                "max_linear_speed is an explicit legacy override; tune the "
                "canonical robot_control control map for normal operation"
            )
        if configured_angular is not None and not math.isclose(
            configured_angular, canonical_angular, rel_tol=1e-6, abs_tol=1e-6
        ):
            self.get_logger().warn(
                "max_angular_speed is derived from the canonical track "
                "geometry; the independent parameter is informational only"
            )

        self._pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self._running = True

        self._key_thread = threading.Thread(target=self._key_loop,
                                            daemon=True)
        self._key_thread.start()
        print(BANNER)

    def _load_control_map(self, configured_path: str) -> ControlMap:
        """Load the canonical map, retaining a source-tree fallback."""
        candidates = []
        if configured_path:
            candidates.append(Path(configured_path))
        candidates.append(
            Path(__file__).resolve().parents[2]
            / "robot_control"
            / "config"
            / "control_map.yaml"
        )
        try:
            from ament_index_python.packages import get_package_share_directory

            candidates.append(
                Path(get_package_share_directory("robot_control"))
                / "config"
                / "control_map.yaml"
            )
        except (ImportError, LookupError, RuntimeError):
            # Direct source-tree tests and non-ROS tooling do not have ament's
            # package index; the sibling-package candidate above is enough.
            pass
        for candidate in candidates:
            if not candidate.is_file():
                continue
            try:
                return load_control_map(candidate)
            except (OSError, ValueError, ImportError):
                pass
        return default_control_map()

    def _positive_float_parameter(self, name: str):
        """Return a finite positive compatibility override, if supplied."""
        try:
            value = float(self.get_parameter(name).value)
        except (TypeError, ValueError):
            return None
        return value if math.isfinite(value) and value > 0.0 else None

    def _get_key(self) -> str:
        # Keep Linux terminal dependencies out of module import time.  This
        # lets Windows CI import and inspect every packaged node while the
        # actual keyboard node still fails clearly if launched without a
        # POSIX terminal implementation.
        try:
            import termios
            import tty
        except ImportError as exc:
            raise RuntimeError(
                "keyboard_teleop requires a POSIX terminal (termios/tty)"
            ) from exc

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
