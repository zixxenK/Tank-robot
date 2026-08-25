#!/usr/bin/env python3
# Copyright 2026 Tank Robot Team
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
"""ROS2 node for path planning using A* or Dijkstra.

The node only emits a command after it has received a current odometry pose.
This keeps a missing localization stream fail-closed instead of driving from
an assumed map-center position.
"""

import math
from typing import Optional
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped, Twist
from nav_msgs.msg import Path as NavPath, OccupancyGrid
from nav_msgs.msg import Odometry
from std_msgs.msg import Header
from navigation.path_planner import GridMap, Point, Path
from navigation.astar_planner import AStarPlanner, DijkstraPlanner
from navigation.simple_planner import SimplePlanner


class PathPlannerNode(Node):
    """ROS2 node for path planning."""

    def __init__(self) -> None:
        super().__init__("path_planner")

        # Parameters
        self.declare_parameter("planner_type", "astar")  # astar, dijkstra, simple
        self.declare_parameter("map_width", 20)  # meters
        self.declare_parameter("map_height", 20)  # meters
        self.declare_parameter("resolution", 0.1)  # meters
        self.declare_parameter("goal_topic", "/goal_pose")
        self.declare_parameter("path_topic", "/planned_path")
        # Autonomous output is a proposal.  The safety gateway accepts it
        # only with an explicit agent heartbeat; /cmd_vel remains the PS5
        # and maintenance teleop lane.
        self.declare_parameter("cmd_vel_topic", "/agent/cmd_vel_proposed")
        self.declare_parameter("odom_topic", "/stm32/odom")
        self.declare_parameter("diagonal", True)
        self.declare_parameter("position_tolerance", 0.12)
        self.declare_parameter("heading_tolerance", 0.20)
        self.declare_parameter("max_linear_speed", 0.25)
        self.declare_parameter("max_angular_speed", 0.8)
        self.declare_parameter("linear_gain", 0.8)
        self.declare_parameter("angular_gain", 1.8)

        self._planner_type = self.get_parameter("planner_type").value
        self._map_width = self.get_parameter("map_width").value
        self._map_height = self.get_parameter("map_height").value
        self._resolution = self.get_parameter("resolution").value
        self._goal_topic = self.get_parameter("goal_topic").value
        self._path_topic = self.get_parameter("path_topic").value
        self._cmd_vel_topic = self.get_parameter("cmd_vel_topic").value
        self._odom_topic = str(self.get_parameter("odom_topic").value)
        self._diagonal = self.get_parameter("diagonal").value
        self._position_tolerance = max(
            0.01, float(self.get_parameter("position_tolerance").value)
        )
        self._heading_tolerance = max(
            0.01, float(self.get_parameter("heading_tolerance").value)
        )
        self._max_linear_speed = max(
            0.0, float(self.get_parameter("max_linear_speed").value)
        )
        self._max_angular_speed = max(
            0.0, float(self.get_parameter("max_angular_speed").value)
        )
        self._linear_gain = max(0.0, float(self.get_parameter("linear_gain").value))
        self._angular_gain = max(0.0, float(self.get_parameter("angular_gain").value))

        # Initialize grid map
        self._grid_map = GridMap(self._map_width, self._map_height, self._resolution)

        # Initialize planner
        if self._planner_type == "astar":
            self._planner = AStarPlanner(self._grid_map, diagonal=self._diagonal)
        elif self._planner_type == "dijkstra":
            self._planner = DijkstraPlanner(self._grid_map, diagonal=self._diagonal)
        else:
            self._planner = SimplePlanner(self._grid_map)

        # Current state
        self._current_path: Optional[Path] = None
        self._current_waypoint_index = 0
        self._goal: Optional[Point] = None
        self._current_pose: Optional[Point] = None
        self._current_yaw = 0.0
        self._has_published_stop = False
        self._map_received = False

        # Subscribers and publishers
        self._goal_sub = self.create_subscription(
            PoseStamped, self._goal_topic, self._goal_callback, 10
        )
        self._map_sub = self.create_subscription(
            OccupancyGrid, "/map", self._map_callback, 10
        )
        self._odom_sub = self.create_subscription(
            Odometry, self._odom_topic, self._odom_callback, 10
        )
        self._path_pub = self.create_publisher(
            NavPath, self._path_topic, 10
        )
        self._cmd_vel_pub = self.create_publisher(
            Twist, self._cmd_vel_topic, 10
        )

        # Timer for path following
        self._timer = self.create_timer(0.1, self._follow_path)

        self.get_logger().info(f"Path planner initialized with {self._planner_type}")

    def _goal_callback(self, msg: PoseStamped) -> None:
        """Process goal pose and plan path."""
        goal = Point(msg.pose.position.x, msg.pose.position.y)
        self._goal = goal

        self._try_plan_goal()

    def _try_plan_goal(self) -> None:
        """Plan only after both localization and a valid map are available."""
        if self._goal is None:
            return
        if self._current_pose is None:
            self._current_path = None
            self._publish_stop()
            self.get_logger().warn(
                "Waiting for odometry before planning the requested goal"
            )
            return
        if not self._map_received:
            self._current_path = None
            self._publish_stop()
            self.get_logger().warn(
                "Waiting for a valid /map before planning the requested goal"
            )
            return

        path = self._planner.plan(self._current_pose, self._goal)

        if path and not path.is_empty():
            self._current_path = path
            self._current_waypoint_index = 0
            self._publish_path(path)
            self.get_logger().info(f"Path planned with {len(path)} waypoints")
            self._has_published_stop = False
        else:
            self._current_path = None
            self._publish_stop()
            self.get_logger().warn("Failed to plan path")

    def _odom_callback(self, msg: Odometry) -> None:
        """Track the current robot pose from the configured odometry topic."""
        position = msg.pose.pose.position
        orientation = msg.pose.pose.orientation
        self._current_pose = Point(float(position.x), float(position.y))
        sin_yaw = 2.0 * (
            float(orientation.w) * float(orientation.z)
            + float(orientation.x) * float(orientation.y)
        )
        cos_yaw = 1.0 - 2.0 * (
            float(orientation.y) ** 2 + float(orientation.z) ** 2
        )
        self._current_yaw = math.atan2(sin_yaw, cos_yaw)

    def _map_callback(self, msg: OccupancyGrid) -> None:
        """Update grid map from occupancy grid."""
        try:
            width = int(msg.info.width)
            height = int(msg.info.height)
            resolution = float(msg.info.resolution)
            data = tuple(msg.data)
        except (AttributeError, TypeError, ValueError, OverflowError) as exc:
            self.get_logger().warn(f"Rejected malformed occupancy grid: {exc}")
            return

        expected_cells = width * height
        if (
            width <= 0
            or height <= 0
            or not math.isfinite(resolution)
            or resolution <= 0.0
            or len(data) != expected_cells
        ):
            self.get_logger().warn(
                "Rejected malformed occupancy grid geometry/data: "
                f"{width}x{height} @ {resolution} with "
                f"{len(data)}/{expected_cells} cells"
            )
            return

        if (
            self._grid_map.grid_width != width
            or self._grid_map.grid_height != height
            or not math.isclose(
                self._grid_map.resolution,
                resolution,
                rel_tol=0.0,
                abs_tol=1e-9,
            )
        ):
            self._grid_map.reconfigure_from_occupancy_grid(
                width, height, resolution
            )
        self._grid_map.clear_all()
        self._grid_map.set_origin(
            Point(msg.info.origin.position.x, msg.info.origin.position.y)
        )

        for i, occupancy in enumerate(data):
            # ROS uses -1 for unknown. Treat unknown as occupied so a partial
            # or unexplored map cannot authorize autonomous motion.
            if occupancy < 0 or occupancy > 50:  # Occupied or unknown
                grid_x = i % width
                grid_y = i // width
                world_x = (
                    (grid_x + 0.5) * resolution
                    + msg.info.origin.position.x
                )
                world_y = (
                    (grid_y + 0.5) * resolution
                    + msg.info.origin.position.y
                )
                self._grid_map.set_obstacle(Point(world_x, world_y))
        self._map_received = True
        self._try_plan_goal()

    def _publish_path(self, path: Path) -> None:
        """Publish path as NavPath message."""
        nav_path = NavPath()
        nav_path.header = Header()
        nav_path.header.stamp = self.get_clock().now().to_msg()
        nav_path.header.frame_id = "map"

        for waypoint in path.waypoints:
            pose = PoseStamped()
            pose.header = nav_path.header
            pose.pose.position.x = waypoint.x
            pose.pose.position.y = waypoint.y
            pose.pose.position.z = 0.0
            pose.pose.orientation.w = 1.0
            nav_path.poses.append(pose)

        self._path_pub.publish(nav_path)

    def _follow_path(self) -> None:
        """Follow the path using current odometry and a bounded controller."""
        if (
            not self._map_received
            or not self._current_path
            or self._current_pose is None
        ):
            self._publish_stop()
            return

        while self._current_waypoint_index < len(self._current_path.waypoints):
            waypoint = self._current_path.waypoints[self._current_waypoint_index]
            if self._current_pose.distance_to(waypoint) > self._position_tolerance:
                break
            self._current_waypoint_index += 1

        if self._current_waypoint_index >= len(self._current_path.waypoints):
            self._current_path = None
            self._publish_stop()
            self.get_logger().info("Path goal reached")
            return

        waypoint = self._current_path.waypoints[self._current_waypoint_index]
        dx = waypoint.x - self._current_pose.x
        dy = waypoint.y - self._current_pose.y
        distance = math.hypot(dx, dy)
        desired_yaw = math.atan2(dy, dx)
        heading_error = math.atan2(
            math.sin(desired_yaw - self._current_yaw),
            math.cos(desired_yaw - self._current_yaw),
        )

        cmd = Twist()
        cmd.angular.z = max(
            -self._max_angular_speed,
            min(
                self._max_angular_speed,
                self._angular_gain * heading_error,
            ),
        )
        if abs(heading_error) <= self._heading_tolerance:
            cmd.linear.x = min(
                self._max_linear_speed,
                self._linear_gain * distance,
            )
        self._cmd_vel_pub.publish(cmd)
        self._has_published_stop = False

    def _publish_stop(self) -> None:
        """Publish one stop command when the planner is idle or unlocalized."""
        if self._has_published_stop:
            return
        self._cmd_vel_pub.publish(Twist())
        self._has_published_stop = True


def main(args=None) -> None:
    rclpy.init(args=args)
    node = PathPlannerNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
