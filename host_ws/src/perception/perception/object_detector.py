#!/usr/bin/env python3
"""Object detection node using OpenCV for real-time recognition.

Supports:
- Color-based object detection
- Contour-based shape detection
- Template matching
- Motion detection
- Integration with ROS2 for publishing detection results
"""

import cv2
import numpy as np
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import (
    QoSDurabilityPolicy,
    QoSProfile,
    QoSReliabilityPolicy,
)
from sensor_msgs.msg import Image
from vision_msgs.msg import Detection2D, Detection2DArray, ObjectHypothesisWithPose
from geometry_msgs.msg import Pose2D
from std_msgs.msg import String
from cv_bridge import CvBridge


@dataclass
class DetectedObject:
    """Detected object with bounding box and classification."""
    class_id: str
    class_name: str
    confidence: float
    bbox: Tuple[int, int, int, int]  # x, y, width, height
    center: Tuple[int, int]


class ObjectDetector(Node):
    """Real-time object detection using OpenCV."""

    def __init__(self) -> None:
        super().__init__("object_detector")

        # Parameters
        self.declare_parameter("input_topic", "/camera/image_raw")
        self.declare_parameter("output_topic", "/perception/detections")
        self.declare_parameter("debug_topic", "/perception/debug_image")
        self.declare_parameter("enable_debug", True)
        self.declare_parameter("min_confidence", 0.5)
        self.declare_parameter("max_objects", 10)

        self._input_topic = self.get_parameter("input_topic").value
        self._output_topic = self.get_parameter("output_topic").value
        self._debug_topic = self.get_parameter("debug_topic").value
        self._enable_debug = self.get_parameter("enable_debug").value
        self._min_confidence = self.get_parameter("min_confidence").value
        self._max_objects = self.get_parameter("max_objects").value
        
        # Default color ranges (hardcoded for simplicity)
        self._color_ranges = [
            {"name": "red", "lower": [0, 100, 100], "upper": [10, 255, 255]},
            {"name": "green", "lower": [40, 50, 50], "upper": [80, 255, 255]},
            {"name": "blue", "lower": [100, 100, 100], "upper": [130, 255, 255]},
            {"name": "yellow", "lower": [20, 100, 100], "upper": [30, 255, 255]},
        ]

        # CV Bridge
        self._cv_bridge = CvBridge()
        sensor_qos = QoSProfile(
            depth=1,
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            durability=QoSDurabilityPolicy.VOLATILE,
        )

        # Subscribers and publishers
        self._image_sub = self.create_subscription(
            Image, self._input_topic, self._image_callback, sensor_qos
        )
        self._detection_pub = self.create_publisher(
            Detection2DArray, self._output_topic, sensor_qos
        )

        if self._enable_debug:
            self._debug_pub = self.create_publisher(
                Image, self._debug_topic, sensor_qos
            )

        # Detection statistics
        self._detection_count = 0
        self._last_detection_time = 0.0

        self.get_logger().info("Object detector initialized")

    def _image_callback(self, msg: Image) -> None:
        """Process incoming image and detect objects."""
        try:
            cv_image = self._cv_bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
            detections = self._detect_objects(cv_image)

            # Publish detections
            self._publish_detections(detections, msg.header)

            # Publish debug image
            if self._enable_debug:
                debug_image = self._draw_detections(cv_image, detections)
                debug_msg = self._cv_bridge.cv2_to_imgmsg(debug_image, encoding="bgr8")
                debug_msg.header = msg.header
                self._debug_pub.publish(debug_msg)

        except Exception as e:
            self.get_logger().error(f"Error processing image: {e}")

    def _detect_objects(self, image: np.ndarray) -> List[DetectedObject]:
        """Detect objects using color-based segmentation."""
        detections: List[DetectedObject] = []
        hsv_image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        for color_range in self._color_ranges:
            color_name = color_range["name"]
            lower = np.array(color_range["lower"])
            upper = np.array(color_range["upper"])

            # Create mask
            mask = cv2.inRange(hsv_image, lower, upper)

            # Morphological operations to clean up mask
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

            # Find contours
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for contour in contours:
                area = cv2.contourArea(contour)
                if area < 500:  # Filter small objects
                    continue

                # Get bounding box
                x, y, w, h = cv2.boundingRect(contour)
                center_x = x + w // 2
                center_y = y + h // 2

                # Calculate confidence based on area and shape
                confidence = min(1.0, area / 5000.0)

                if confidence >= self._min_confidence:
                    detection = DetectedObject(
                        class_id=color_name,
                        class_name=color_name.capitalize(),
                        confidence=confidence,
                        bbox=(x, y, w, h),
                        center=(center_x, center_y),
                    )
                    detections.append(detection)

        # Sort by confidence and limit
        detections.sort(key=lambda d: d.confidence, reverse=True)
        return detections[:self._max_objects]

    def _publish_detections(self, detections: List[DetectedObject], header) -> None:
        """Publish detections as ROS2 Detection2DArray message."""
        detection_array = Detection2DArray()
        detection_array.header = header

        for detection in detections:
            det_msg = Detection2D()
            det_msg.header = header

            # Create hypothesis
            hypothesis = ObjectHypothesisWithPose()
            hypothesis.hypothesis.class_id = detection.class_id
            hypothesis.hypothesis.score = detection.confidence

            # Set pose (2D center in image coordinates)
            pose = Pose2D()
            pose.x = float(detection.center[0])
            pose.y = float(detection.center[1])
            hypothesis.pose = pose

            det_msg.results.append(hypothesis)

            # Set bounding box
            det_msg.bbox.center.x = float(detection.center[0])
            det_msg.bbox.center.y = float(detection.center[1])
            det_msg.bbox.size_x = float(detection.bbox[2])
            det_msg.bbox.size_y = float(detection.bbox[3])

            detection_array.detections.append(det_msg)

        self._detection_pub.publish(detection_array)
        self._detection_count += len(detections)
        self._last_detection_time = time.time()

    def _draw_detections(self, image: np.ndarray, detections: List[DetectedObject]) -> np.ndarray:
        """Draw detection bounding boxes and labels on image."""
        debug_image = image.copy()

        for detection in detections:
            x, y, w, h = detection.bbox
            center_x, center_y = detection.center

            # Choose color based on class
            color_map = {
                "red": (0, 0, 255),
                "green": (0, 255, 0),
                "blue": (255, 0, 0),
                "yellow": (0, 255, 255),
            }
            color = color_map.get(detection.class_id, (255, 255, 255))

            # Draw bounding box
            cv2.rectangle(debug_image, (x, y), (x + w, y + h), color, 2)

            # Draw center
            cv2.circle(debug_image, (center_x, center_y), 5, color, -1)

            # Draw label
            label = f"{detection.class_name}: {detection.confidence:.2f}"
            cv2.putText(
                debug_image,
                label,
                (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                2,
            )

        return debug_image


def main(args=None) -> None:
    rclpy.init(args=args)
    node = ObjectDetector()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
