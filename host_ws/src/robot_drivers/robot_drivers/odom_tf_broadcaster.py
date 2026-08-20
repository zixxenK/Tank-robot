"""Broadcast the odom-to-base transform carried by STM32 odometry."""

from __future__ import annotations

from typing import Optional

import rclpy
from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from tf2_ros import TransformBroadcaster


class OdomTfBroadcaster(Node):
    """Turn the bridge's Odometry messages into the TF required by SLAM."""

    def __init__(self) -> None:
        super().__init__("odom_tf_broadcaster")
        self.declare_parameter("odom_topic", "/stm32/odom")
        self.declare_parameter("odom_frame", "odom")
        self.declare_parameter("base_frame", "base_link")
        topic = str(self.get_parameter("odom_topic").value)
        self._odom_frame = str(self.get_parameter("odom_frame").value)
        self._base_frame = str(self.get_parameter("base_frame").value)
        self._broadcaster = TransformBroadcaster(self)
        self._subscription = self.create_subscription(
            Odometry, topic, self._on_odometry, 10
        )
        self.get_logger().info(
            f"Broadcasting {self._odom_frame} -> {self._base_frame} from {topic}"
        )

    def _on_odometry(self, message: Odometry) -> None:
        """Publish a transform with the odometry message's original timestamp."""
        transform = TransformStamped()
        transform.header = message.header
        transform.header.frame_id = message.header.frame_id or self._odom_frame
        transform.child_frame_id = message.child_frame_id or self._base_frame
        transform.transform.translation.x = message.pose.pose.position.x
        transform.transform.translation.y = message.pose.pose.position.y
        transform.transform.translation.z = message.pose.pose.position.z
        transform.transform.rotation = message.pose.pose.orientation
        self._broadcaster.sendTransform(transform)


def main(args: Optional[list[str]] = None) -> None:
    """Run the odometry TF broadcaster."""
    rclpy.init(args=args)
    node = OdomTfBroadcaster()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
