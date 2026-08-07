#!/usr/bin/env python3
"""ROS2 node for path planning using A* or Dijkstra."""

from typing import Optional
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped, Twist
from nav_msgs.msg import Path as NavPath, OccupancyGrid
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
        self.declare_parameter("cmd_vel_topic", "/cmd_vel")
        self.declare_parameter("diagonal", True)

        self._planner_type = self.get_parameter("planner_type").value
        self._map_width = self.get_parameter("map_width").value
        self._map_height = self.get_parameter("map_height").value
        self._resolution = self.get_parameter("resolution").value
        self._goal_topic = self.get_parameter("goal_topic").value
        self._path_topic = self.get_parameter("path_topic").value
        self._cmd_vel_topic = self.get_parameter("cmd_vel_topic").value
        self._diagonal = self.get_parameter("diagonal").value

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

        # Subscribers and publishers
        self._goal_sub = self.create_subscription(
            PoseStamped, self._goal_topic, self._goal_callback, 10
        )
        self._map_sub = self.create_subscription(
            OccupancyGrid, "/map", self._map_callback, 10
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

        # Assume robot starts at center of map (should be replaced with actual odometry)
        start = Point(self._map_width / 2, self._map_height / 2)

        # Plan path
        path = self._planner.plan(start, goal)

        if path and not path.is_empty():
            self._current_path = path
            self._current_waypoint_index = 0
            self._publish_path(path)
            self.get_logger().info(f"Path planned with {len(path)} waypoints")
        else:
            self.get_logger().warn("Failed to plan path")

    def _map_callback(self, msg: OccupancyGrid) -> None:
        """Update grid map from occupancy grid."""
        self._grid_map.clear_all()

        for i, occupancy in enumerate(msg.data):
            if occupancy > 50:  # Occupied threshold
                grid_x = i % msg.info.width
                grid_y = i // msg.info.width
                world_x = grid_x * msg.info.resolution + msg.info.origin.position.x
                world_y = grid_y * msg.info.resolution + msg.info.origin.position.y
                self._grid_map.set_obstacle(Point(world_x, world_y))

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
        """Follow current path by publishing velocity commands."""
        if not self._current_path or self._current_waypoint_index >= len(self._current_path.waypoints):
            return

        # Get current waypoint
        waypoint = self._current_path.waypoints[self._current_waypoint_index]

        # Simple proportional controller to move toward waypoint
        # (In real implementation, this would use actual robot pose from odometry)
        cmd = Twist()
        cmd.linear.x = 0.3  # Constant forward speed
        cmd.angular.z = 0.0

        self._cmd_vel_pub.publish(cmd)

        # Move to next waypoint (simplified - should check distance to waypoint)
        self._current_waypoint_index += 1


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
