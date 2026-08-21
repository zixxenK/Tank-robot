#!/usr/bin/env python3
"""
Bridge the ESP32 MJPEG stream to /camera/image_raw.

Connects to the ESP32-S3 camera's MJPEG HTTP stream, decodes each JPEG
frame, and publishes it as a sensor_msgs/Image on /camera/image_raw.
"""

import threading
import time
import urllib.request

import cv2
import numpy as np
from cv_bridge import CvBridge
import rclpy
from rclpy.node import Node
from rclpy.qos import (
    QoSDurabilityPolicy,
    QoSProfile,
    QoSReliabilityPolicy,
)
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from sensor_msgs.msg import Image


MAX_MJPEG_BUFFER_BYTES = 8 * 1024 * 1024
FRAME_FRESHNESS_TIMEOUT_S = 5.0


class ESP32CameraBridge(Node):
    """Streams MJPEG from ESP32 camera and republishes as ROS Image."""

    def __init__(self):
        super().__init__("esp32_camera_bridge")

        self.declare_parameter("camera_ip", "192.168.1.125")
        self.declare_parameter("stream_port", 81)
        self.declare_parameter("stream_path", "/stream")

        ip = self.get_parameter("camera_ip").value
        port = self.get_parameter("stream_port").value
        path = self.get_parameter("stream_path").value

        self._url = f"http://{ip}:{port}{path}"
        image_qos = QoSProfile(
            depth=1,
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            durability=QoSDurabilityPolicy.VOLATILE,
        )
        self._pub = self.create_publisher(
            Image,
            "/camera/image_raw",
            image_qos,
        )
        self._diagnostics_pub = self.create_publisher(
            DiagnosticArray, "/camera/diagnostics", 10
        )
        self._running = True
        self._bridge = CvBridge()
        self._frame_count = 0
        self._decode_errors = 0
        self._stream_errors = 0
        self._stream_connected = False
        self._last_frame_time = 0.0

        self._thread = threading.Thread(target=self._stream_loop, daemon=True)
        self._thread.start()
        self._diagnostics_timer = self.create_timer(
            2.0, self._publish_diagnostics
        )
        self.get_logger().info(f"Camera bridge connecting to {self._url}")

    def _stream_loop(self):
        boundary = b"--frame"
        while self._running:
            try:
                with urllib.request.urlopen(self._url, timeout=10) as resp:
                    self._stream_connected = True
                    buf = b""
                    while self._running:
                        chunk = resp.read(4096)
                        if not chunk:
                            break
                        buf += chunk
                        if len(buf) > MAX_MJPEG_BUFFER_BYTES:
                            # Preserve the newest possible frame boundary and
                            # discard an unbounded malformed prefix.
                            boundary_start = buf.rfind(boundary)
                            if boundary_start >= 0:
                                buf = buf[boundary_start:]
                            else:
                                buf = buf[-MAX_MJPEG_BUFFER_BYTES:]
                            self._stream_errors += 1
                            self.get_logger().warn(
                                "MJPEG parser buffer exceeded limit; "
                                "discarded stale stream data"
                            )

                        # Parse MJPEG boundary
                        while boundary in buf:
                            _, after = buf.split(boundary, 1)
                            # Find end of part headers
                            header_end = after.find(b"\r\n\r\n")
                            if header_end == -1:
                                buf = boundary + after
                                break
                            payload = after[header_end + 4:]
                            # Find start of next boundary
                            next_bound = payload.find(boundary)
                            if next_bound == -1:
                                buf = boundary + after
                                break
                            jpeg = payload[:next_bound].rstrip(b"\r\n")
                            buf = payload[next_bound:]
                            self._publish_frame(jpeg)
                self._stream_connected = False
                if self._running:
                    self._stop_wait(2.0)

            except Exception as exc:  # noqa: BLE001
                self._stream_connected = False
                self._stream_errors += 1
                if self._running:
                    self.get_logger().warn(
                        f"Camera stream error: {exc} — retrying in 2s"
                    )
                    time.sleep(2.0)

    def _publish_frame(self, jpeg_bytes: bytes):
        frame = cv2.imdecode(
            np.frombuffer(jpeg_bytes, dtype=np.uint8), cv2.IMREAD_COLOR
        )
        if frame is None:
            self._decode_errors += 1
            self.get_logger().warn("Dropped invalid JPEG frame from ESP32")
            return

        msg = self._bridge.cv2_to_imgmsg(frame, encoding="bgr8")
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "camera_link"
        self._pub.publish(msg)
        self._frame_count += 1
        self._last_frame_time = time.monotonic()

    def _stop_wait(self, seconds: float) -> None:
        """Wait between reconnects without delaying shutdown unnecessarily."""
        deadline = time.monotonic() + max(0.0, seconds)
        while self._running:
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                return
            time.sleep(min(0.1, remaining))

    def _publish_diagnostics(self):
        """Publish stream and frame counters for dashboard health checks."""
        status = DiagnosticStatus()
        status.name = "esp32_camera_bridge: ESP32 camera"
        frame_fresh = (
            self._last_frame_time > 0.0
            and time.monotonic() - self._last_frame_time
            <= FRAME_FRESHNESS_TIMEOUT_S
        )
        if self._stream_connected and frame_fresh:
            status.level = DiagnosticStatus.OK
            status.message = "Streaming frames"
        elif self._stream_connected:
            status.level = DiagnosticStatus.WARN
            status.message = "Connected but no decoded frame yet"
        else:
            status.level = DiagnosticStatus.ERROR
            status.message = "ESP32 stream disconnected"
        status.values.extend(
            [
                KeyValue(key="url", value=self._url),
                KeyValue(
                    key="stream_connected",
                    value=str(self._stream_connected),
                ),
                KeyValue(key="frames", value=str(self._frame_count)),
                KeyValue(key="frame_fresh", value=str(frame_fresh)),
                KeyValue(key="decode_errors", value=str(self._decode_errors)),
                KeyValue(key="stream_errors", value=str(self._stream_errors)),
            ]
        )
        diagnostics = DiagnosticArray()
        diagnostics.header.stamp = self.get_clock().now().to_msg()
        diagnostics.status.append(status)
        self._diagnostics_pub.publish(diagnostics)

    def destroy_node(self):
        self._running = False
        if hasattr(self, "_diagnostics_timer"):
            self._diagnostics_timer.cancel()
        if hasattr(self, "_thread") and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = ESP32CameraBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
