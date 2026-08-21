"""Contract tests for the repository's offline ROS compatibility layer."""

import numpy as np

from cv_bridge import CvBridge
from geometry_msgs.msg import PoseStamped, TransformStamped
from nav_msgs.msg import OccupancyGrid, Path
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage, Image
from std_msgs.msg import String
from tf2_ros import TransformBroadcaster


def test_stub_node_preserves_parameters_and_published_messages():
    node = Node("contract_test")
    node.declare_parameter("answer", 42)
    assert node.get_parameter("answer").value == 42

    publisher = node.create_publisher(String, "/contract", 1)
    message = String("ready")
    publisher.publish(message)
    assert publisher.last_msg is message
    assert publisher.messages == [message]


def test_stub_messages_cover_image_navigation_and_tf_paths():
    image = Image()
    image.width = 2
    image.height = 2
    image.encoding = "bgr8"
    image.step = 6
    image.data = bytes(12)
    assert isinstance(image, Image)
    assert isinstance(CompressedImage(), CompressedImage)
    assert isinstance(PoseStamped(), PoseStamped)
    assert isinstance(Path(), Path)
    assert isinstance(OccupancyGrid(), OccupancyGrid)

    transform = TransformStamped()
    broadcaster = TransformBroadcaster()
    broadcaster.sendTransform(transform)
    assert broadcaster.transforms == [transform]


def test_stub_cv_bridge_round_trips_a_bgr_image():
    bridge = CvBridge()
    source = np.zeros((2, 3, 3), dtype=np.uint8)
    source[0, 1] = (10, 20, 30)
    message = bridge.cv2_to_imgmsg(source, encoding="bgr8")
    restored = bridge.imgmsg_to_cv2(message, desired_encoding="bgr8")
    assert np.array_equal(source, restored)
