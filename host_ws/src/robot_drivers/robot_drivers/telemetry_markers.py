#!/usr/bin/env python3
# pyright: reportMissingImports=false, reportMissingModuleSource=false
# pyright: reportMissingTypeStubs=false
# pylint: disable=import-error,assignment-from-no-return
"""Publish RViz-friendly markers for cmd_vel and encoder telemetry."""

import rclpy
from geometry_msgs.msg import Point
from geometry_msgs.msg import Twist
from rclpy.node import Node
from std_msgs.msg import Bool
from std_msgs.msg import Int32MultiArray
from visualization_msgs.msg import Marker
from visualization_msgs.msg import MarkerArray


class TelemetryMarkers(Node):
    """Convert bridge telemetry topics into RViz marker overlays."""

    def __init__(self):
        super().__init__("telemetry_markers")

        self.declare_parameter("frame_id", "base_link")
        self.declare_parameter("marker_topic", "/telemetry/markers")
        self.declare_parameter("publish_rate_hz", 10.0)
        self.declare_parameter("enable_encoder_telemetry", True)
        self.declare_parameter("enable_bridge_alive", True)

        self._frame_id = self.get_parameter("frame_id").value
        self._marker_topic = self.get_parameter("marker_topic").value
        self._publish_rate_hz = float(
            self.get_parameter("publish_rate_hz").value
        )
        self._enable_encoder_telemetry = bool(
            self.get_parameter("enable_encoder_telemetry").value
        )
        self._enable_bridge_alive = bool(
            self.get_parameter("enable_bridge_alive").value
        )

        self._cmd_vel = Twist()
        self._encoder_left = 0
        self._encoder_right = 0
        self._bridge_alive = False

        self.create_subscription(Twist, "/cmd_vel", self._cmd_cb, 10)
        if self._enable_encoder_telemetry:
            self.create_subscription(
                Int32MultiArray, "/stm32/encoder_ticks", self._enc_cb, 10
            )
        if self._enable_bridge_alive:
            self.create_subscription(
                Bool,
                "/stm32/bridge_alive",
                self._alive_cb,
                10,
            )

        self._pub = self.create_publisher(MarkerArray, self._marker_topic, 10)
        period = 1.0 / max(1.0, self._publish_rate_hz)
        self.create_timer(period, self._publish)

    def _cmd_cb(self, msg: Twist):
        self._cmd_vel = msg

    def _enc_cb(self, msg: Int32MultiArray):
        if len(msg.data) >= 2:
            self._encoder_left = int(msg.data[0])
            self._encoder_right = int(msg.data[1])

    def _alive_cb(self, msg: Bool):
        self._bridge_alive = bool(msg.data)

    def _publish(self):
        now = self.get_clock().now().to_msg()

        markers = MarkerArray()

        arrow = Marker()
        arrow.header.frame_id = self._frame_id
        arrow.header.stamp = now
        arrow.ns = "telemetry_cmd"
        arrow.id = 1
        arrow.type = Marker.ARROW
        arrow.action = Marker.ADD

        vx = float(self._cmd_vel.linear.x)
        wz = float(self._cmd_vel.angular.z)
        length = max(0.05, min(1.2, abs(vx) * 1.8))

        start = Point()
        start.x = 0.0
        start.y = 0.0
        start.z = 0.18

        end = Point()
        end.x = length if vx >= 0.0 else -length
        end.y = max(-0.5, min(0.5, wz * 0.08))
        end.z = 0.18

        arrow.points = [start, end]
        arrow.scale.x = 0.03
        arrow.scale.y = 0.06
        arrow.scale.z = 0.08
        arrow.color.a = 0.95
        arrow.color.r = 0.1
        arrow.color.g = 0.8 if self._bridge_alive else 0.3
        arrow.color.b = 0.2 if self._bridge_alive else 0.8

        text = Marker()
        text.header.frame_id = self._frame_id
        text.header.stamp = now
        text.ns = "telemetry_text"
        text.id = 2
        text.type = Marker.TEXT_VIEW_FACING
        text.action = Marker.ADD
        text.pose.position.x = 0.0
        text.pose.position.y = 0.0
        text.pose.position.z = 0.40
        text.scale.z = 0.07
        text.color.a = 1.0
        text.color.r = 1.0
        text.color.g = 1.0
        text.color.b = 1.0
        text.text = (
            f"cmd_vel vx={vx:+.2f} m/s wz={wz:+.2f} rad/s\\n"
            f"enc L={self._encoder_left} R={self._encoder_right}\\n"
            f"bridge_alive={str(self._bridge_alive).lower()}"
        )

        markers.markers.append(arrow)
        markers.markers.append(text)
        self._pub.publish(markers)


def main(args=None):
    _ = args
    rclpy.init()
    node = TelemetryMarkers()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
