#!/usr/bin/env python3
"""esp32_camera_bridge.py — ESP32 MJPEG stream → /camera/image_raw bridge.

Connects to the ESP32-S3 camera's MJPEG HTTP stream, decodes each JPEG
frame, and publishes it as a sensor_msgs/Image on /camera/image_raw.
"""

import urllib.request
import threading

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import Header


class ESP32CameraBridge(Node):
    """Streams MJPEG from ESP32 camera and republishes as ROS Image."""

    def __init__(self):
        super().__init__("esp32_camera_bridge")

        self.declare_parameter("camera_ip",   "192.168.1.153")
        self.declare_parameter("stream_port", 81)
        self.declare_parameter("stream_path", "/stream")

        ip   = self.get_parameter("camera_ip").value
        port = self.get_parameter("stream_port").value
        path = self.get_parameter("stream_path").value

        self._url = f"http://{ip}:{port}{path}"
        self._pub = self.create_publisher(Image, "/camera/image_raw", 10)
        self._running = True

        self._thread = threading.Thread(target=self._stream_loop,
                                        daemon=True)
        self._thread.start()
        self.get_logger().info(f"Camera bridge connecting to {self._url}")

    def _stream_loop(self):
        boundary = b"--frame"
        while self._running:
            try:
                with urllib.request.urlopen(self._url, timeout=10) as resp:
                    buf = b""
                    while self._running:
                        chunk = resp.read(4096)
                        if not chunk:
                            break
                        buf += chunk

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
                            buf  = payload[next_bound:]
                            self._publish_frame(jpeg)

            except Exception as exc:  # noqa: BLE001
                if self._running:
                    self.get_logger().warn(
                        f"Camera stream error: {exc} — retrying in 2s"
                    )
                    import time
                    time.sleep(2.0)

    def _publish_frame(self, jpeg_bytes: bytes):
        msg = Image()
        msg.header = Header()
        msg.header.stamp    = self.get_clock().now().to_msg()
        msg.header.frame_id = "camera_link"
        msg.encoding        = "jpeg"
        msg.data            = list(jpeg_bytes)
        msg.step            = 0
        # Width/height unknown without decoding; set to 0
        msg.width           = 0
        msg.height          = 0
        self._pub.publish(msg)

    def destroy_node(self):
        self._running = False
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
