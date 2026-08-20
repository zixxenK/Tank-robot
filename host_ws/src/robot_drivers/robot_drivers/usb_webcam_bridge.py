"""Publish a USB V4L2 webcam as a ROS 2 image topic."""

import threading

import cv2
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, QoSReliabilityPolicy
from sensor_msgs.msg import Image


class UsbWebcamBridge(Node):
    """Capture a USB webcam connected to the Rock64 hub."""

    def __init__(self) -> None:
        """Open the configured V4L2 device and start capture."""
        super().__init__("usb_webcam_bridge")
        self.declare_parameter("device", "/dev/video0")
        self.declare_parameter("topic", "/camera/usb/image_raw")
        self.declare_parameter("frame_id", "usb_camera_link")
        self.declare_parameter("width", 640)
        self.declare_parameter("height", 480)
        self.declare_parameter("fps", 15.0)

        self._device = self.get_parameter("device").value
        self._topic = self.get_parameter("topic").value
        self._frame_id = self.get_parameter("frame_id").value
        self._width = int(self.get_parameter("width").value)
        self._height = int(self.get_parameter("height").value)
        self._fps = float(self.get_parameter("fps").value)
        image_qos = QoSProfile(
            depth=1,
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            durability=QoSDurabilityPolicy.VOLATILE,
        )
        self._publisher = self.create_publisher(Image, self._topic, image_qos)
        self._bridge = CvBridge()
        self._capture = None
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._capture_loop,
            name="usb-webcam",
            daemon=True,
        )
        self._thread.start()

    def _capture_loop(self) -> None:
        """Capture frames and reconnect after USB disconnects."""
        while not self._stop.is_set():
            capture = cv2.VideoCapture(self._device, cv2.CAP_V4L2)
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
            capture.set(cv2.CAP_PROP_FPS, self._fps)
            if not capture.isOpened():
                capture.release()
                self.get_logger().warn(
                    f"USB webcam unavailable at {self._device}; retrying"
                )
                self._stop.wait(2.0)
                continue

            self.get_logger().info(
                f"USB webcam publishing {self._device} on {self._topic}"
            )
            self._capture = capture
            period = 1.0 / max(self._fps, 1.0)
            while not self._stop.is_set():
                ok, frame = capture.read()
                if not ok:
                    break
                message = self._bridge.cv2_to_imgmsg(frame, encoding="bgr8")
                message.header.stamp = self.get_clock().now().to_msg()
                message.header.frame_id = self._frame_id
                self._publisher.publish(message)
                self._stop.wait(period)
            capture.release()
            self._capture = None

    def destroy_node(self):
        """Stop capture before destroying the ROS node."""
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2.0)
        super().destroy_node()


def main(args=None) -> None:
    """Run the USB webcam bridge."""
    rclpy.init(args=args)
    node = UsbWebcamBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
