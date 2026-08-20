"""Republish ROS images as bounded JPEG CompressedImage topics.

The Rock64 keeps the existing raw image topics for local ROS consumers, while
the compressed topics are the intended LAN transport for Foxglove on the PC.
The queue is deliberately depth one so an overloaded network cannot
accumulate stale frames.
"""

from __future__ import annotations

from typing import Optional

import cv2
from cv_bridge import CvBridge
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, QoSReliabilityPolicy
from sensor_msgs.msg import CompressedImage, Image


class CompressedImageBridge(Node):
    """Convert one raw ROS image stream into a best-effort JPEG stream."""

    def __init__(self) -> None:
        super().__init__("compressed_image_bridge")
        self.declare_parameter("input_topic", "/camera/image_raw")
        self.declare_parameter("output_topic", "/camera/image_raw/compressed")
        self.declare_parameter("jpeg_quality", 70)
        self.declare_parameter("frame_id", "")

        input_topic = str(self.get_parameter("input_topic").value)
        output_topic = str(self.get_parameter("output_topic").value)
        self._quality = max(
            1, min(100, int(self.get_parameter("jpeg_quality").value))
        )
        self._frame_id = str(self.get_parameter("frame_id").value or "")
        qos = QoSProfile(
            depth=1,
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            durability=QoSDurabilityPolicy.VOLATILE,
        )
        self._publisher = self.create_publisher(CompressedImage, output_topic, qos)
        self._bridge = CvBridge()
        self._subscription = self.create_subscription(
            Image, input_topic, self._on_image, qos
        )
        self.get_logger().info(
            f"Compressing {input_topic} -> {output_topic} at JPEG quality "
            f"{self._quality}"
        )

    def _on_image(self, message: Image) -> None:
        """Encode and publish one frame, dropping invalid/unsupported frames."""
        try:
            frame = self._bridge.imgmsg_to_cv2(message, desired_encoding="bgr8")
            ok, encoded = cv2.imencode(
                ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), self._quality]
            )
            if not ok:
                self.get_logger().warning("OpenCV could not encode camera frame")
                return
        except Exception as exc:  # noqa: BLE001 - keep a bad frame non-fatal
            self.get_logger().warning(f"Dropped image during JPEG conversion: {exc}")
            return

        compressed = CompressedImage()
        compressed.header = message.header
        if self._frame_id:
            compressed.header.frame_id = self._frame_id
        compressed.format = "jpeg"
        compressed.data = encoded.tobytes()
        self._publisher.publish(compressed)


def main(args: Optional[list[str]] = None) -> None:
    """Run the image compression bridge."""
    rclpy.init(args=args)
    node = CompressedImageBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
