#!/usr/bin/env python3
"""Obstacle detection using camera and depth estimation.

Provides:
- Edge-based obstacle detection
- Motion-based obstacle detection
- Depth estimation from stereo or monocular cues
- Fusion with IMU data for terrain analysis
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
from geometry_msgs.msg import Twist
from std_msgs.msg import Float32MultiArray
from cv_bridge import CvBridge


@dataclass
class Obstacle:
    """Detected obstacle with position and severity."""
    center_x: int
    center_y: int
    width: int
    height: int
    distance: float  # Estimated distance
    severity: float  # 0.0 to 1.0


class ObstacleDetector(Node):
    """Obstacle detection node for robot navigation."""

    def __init__(self) -> None:
        super().__init__("obstacle_detector")

        # Parameters
        self.declare_parameter("input_topic", "/camera/image_raw")
        self.declare_parameter("output_topic", "/perception/obstacles")
        self.declare_parameter("avoidance_topic", "/perception/avoidance_vector")
        self.declare_parameter("enable_debug", True)
        self.declare_parameter("min_obstacle_area", 1000)
        self.declare_parameter("max_distance", 3.0)  # meters
        self.declare_parameter("fov_horizontal", 60.0)  # degrees
        self.declare_parameter("fov_vertical", 45.0)  # degrees

        self._input_topic = self.get_parameter("input_topic").value
        self._output_topic = self.get_parameter("output_topic").value
        self._avoidance_topic = self.get_parameter("avoidance_topic").value
        self._enable_debug = self.get_parameter("enable_debug").value
        self._min_obstacle_area = self.get_parameter("min_obstacle_area").value
        self._max_distance = self.get_parameter("max_distance").value
        self._fov_horizontal = self.get_parameter("fov_horizontal").value
        self._fov_vertical = self.get_parameter("fov_vertical").value

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
        self._obstacle_pub = self.create_publisher(
            Float32MultiArray, self._output_topic, sensor_qos
        )
        self._avoidance_pub = self.create_publisher(
            Twist, self._avoidance_topic, sensor_qos
        )

        if self._enable_debug:
            self._debug_pub = self.create_publisher(
                Image, "/perception/obstacle_debug", sensor_qos
            )

        # Previous frame for motion detection
        self._prev_frame: Optional[np.ndarray] = None
        self._prev_gray: Optional[np.ndarray] = None

        self.get_logger().info("Obstacle detector initialized")

    def _image_callback(self, msg: Image) -> None:
        """Process incoming image and detect obstacles."""
        try:
            cv_image = self._cv_bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
            obstacles = self._detect_obstacles(cv_image)

            # Publish obstacle data
            self._publish_obstacles(obstacles)

            # Compute and publish avoidance vector
            avoidance_cmd = self._compute_avoidance(obstacles, cv_image.shape)
            self._avoidance_pub.publish(avoidance_cmd)

            # Publish debug image
            if self._enable_debug:
                debug_image = self._draw_obstacles(cv_image, obstacles)
                debug_msg = self._cv_bridge.cv2_to_imgmsg(debug_image, encoding="bgr8")
                debug_msg.header = msg.header
                self._debug_pub.publish(debug_msg)

        except Exception as e:
            self.get_logger().error(f"Error processing image: {e}")

    def _detect_obstacles(self, image: np.ndarray) -> List[Obstacle]:
        """Detect obstacles using edge and motion detection."""
        obstacles: List[Obstacle] = []

        # Edge-based detection
        edge_obstacles = self._detect_edge_obstacles(image)
        obstacles.extend(edge_obstacles)

        # Motion-based detection
        motion_obstacles = self._detect_motion_obstacles(image)
        obstacles.extend(motion_obstacles)

        # Merge nearby obstacles
        obstacles = self._merge_obstacles(obstacles)

        return obstacles

    def _detect_edge_obstacles(self, image: np.ndarray) -> List[Obstacle]:
        """Detect obstacles using edge detection."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Canny edge detection
        edges = cv2.Canny(blurred, 50, 150)

        # Find contours
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        obstacles = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < self._min_obstacle_area:
                continue

            x, y, w, h = cv2.boundingRect(contour)
            center_x = x + w // 2
            center_y = y + h // 2

            # Estimate distance based on vertical position (assuming camera mounted at angle)
            distance = self._estimate_distance(center_y, image.shape[0])

            # Calculate severity based on size and distance
            severity = min(1.0, (area / 10000.0) * (self._max_distance / distance))

            obstacle = Obstacle(
                center_x=center_x,
                center_y=center_y,
                width=w,
                height=h,
                distance=distance,
                severity=severity,
            )
            obstacles.append(obstacle)

        return obstacles

    def _detect_motion_obstacles(self, image: np.ndarray) -> List[Obstacle]:
        """Detect moving obstacles using frame differencing."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        if self._prev_gray is None:
            self._prev_gray = gray
            return []

        # Frame differencing
        diff = cv2.absdiff(self._prev_gray, gray)

        # Threshold
        _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)

        # Morphological operations
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

        # Find contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        obstacles = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < self._min_obstacle_area:
                continue

            x, y, w, h = cv2.boundingRect(contour)
            center_x = x + w // 2
            center_y = y + h // 2

            distance = self._estimate_distance(center_y, image.shape[0])
            severity = min(1.0, (area / 5000.0) * (self._max_distance / distance))

            obstacle = Obstacle(
                center_x=center_x,
                center_y=center_y,
                width=w,
                height=h,
                distance=distance,
                severity=severity,
            )
            obstacles.append(obstacle)

        self._prev_gray = gray
        return obstacles

    def _estimate_distance(self, y: int, image_height: int) -> float:
        """Estimate distance based on vertical position in image."""
        # Simple linear model: closer objects appear lower in the image
        # This is a rough approximation - would need calibration for real use
        normalized_y = y / image_height
        distance = self._max_distance * (1.0 - normalized_y)
        return max(0.1, min(self._max_distance, distance))

    def _merge_obstacles(self, obstacles: List[Obstacle]) -> List[Obstacle]:
        """Merge overlapping or nearby obstacles."""
        if not obstacles:
            return []

        # Sort by x position
        obstacles.sort(key=lambda o: o.center_x)

        merged = []
        current = obstacles[0]

        for obstacle in obstacles[1:]:
            # Check if obstacles overlap
            overlap_x = abs(current.center_x - obstacle.center_x) < (current.width + obstacle.width) / 2
            overlap_y = abs(current.center_y - obstacle.center_y) < (current.height + obstacle.height) / 2

            if overlap_x and overlap_y:
                # Merge obstacles
                current = Obstacle(
                    center_x=(current.center_x + obstacle.center_x) // 2,
                    center_y=(current.center_y + obstacle.center_y) // 2,
                    width=max(current.width, obstacle.width),
                    height=max(current.height, obstacle.height),
                    distance=min(current.distance, obstacle.distance),
                    severity=max(current.severity, obstacle.severity),
                )
            else:
                merged.append(current)
                current = obstacle

        merged.append(current)
        return merged

    def _publish_obstacles(self, obstacles: List[Obstacle]) -> None:
        """Publish obstacle data as Float32MultiArray."""
        msg = Float32MultiArray()

        # Format: [x, y, width, height, distance, severity, ...] for each obstacle
        for obstacle in obstacles:
            msg.data.extend([
                float(obstacle.center_x),
                float(obstacle.center_y),
                float(obstacle.width),
                float(obstacle.height),
                float(obstacle.distance),
                float(obstacle.severity),
            ])

        self._obstacle_pub.publish(msg)

    def _compute_avoidance(self, obstacles: List[Obstacle], image_shape: Tuple[int, int, int]) -> Twist:
        """Compute avoidance command based on detected obstacles."""
        cmd = Twist()

        if not obstacles:
            return cmd

        # Find the most severe obstacle
        most_severe = max(obstacles, key=lambda o: o.severity)

        # Compute avoidance vector
        image_center_x = image_shape[1] // 2
        obstacle_offset = most_severe.center_x - image_center_x

        # If obstacle is close and severe, turn away
        if most_severe.distance < 1.0 and most_severe.severity > 0.5:
            # Turn away from obstacle
            turn_direction = -1.0 if obstacle_offset > 0 else 1.0
            cmd.angular.z = turn_direction * 0.5 * most_severe.severity
            cmd.linear.x = 0.2 * (1.0 - most_severe.severity)  # Slow down

        return cmd

    def _draw_obstacles(self, image: np.ndarray, obstacles: List[Obstacle]) -> np.ndarray:
        """Draw obstacle bounding boxes on image."""
        debug_image = image.copy()

        for obstacle in obstacles:
            x = obstacle.center_x - obstacle.width // 2
            y = obstacle.center_y - obstacle.height // 2

            # Color based on severity (green to red)
            color = (
                int(255 * obstacle.severity),
                int(255 * (1.0 - obstacle.severity)),
                0,
            )

            # Draw bounding box
            cv2.rectangle(
                debug_image,
                (x, y),
                (x + obstacle.width, y + obstacle.height),
                color,
                2,
            )

            # Draw center
            cv2.circle(debug_image, (obstacle.center_x, obstacle.center_y), 5, color, -1)

            # Draw distance and severity
            label = f"{obstacle.distance:.1f}m {obstacle.severity:.2f}"
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
    node = ObstacleDetector()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
