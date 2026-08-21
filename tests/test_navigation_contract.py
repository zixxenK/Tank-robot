"""Offline tests for navigation bounds, planning, and fail-closed following."""

import importlib.util
from pathlib import Path

from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Odometry
from nav_msgs.msg import OccupancyGrid

from navigation.astar_planner import AStarPlanner
from navigation.path_planner import GridMap, Point


ROOT = Path(__file__).resolve().parents[1]


def _planner_node_class():
    path = ROOT / "host_ws" / "src" / "navigation" / "scripts" / "path_planner.py"
    spec = importlib.util.spec_from_file_location("navigation_node_contract", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.PathPlannerNode


def test_grid_map_uses_floor_and_blocks_diagonal_corner_cutting():
    grid = GridMap(2, 2, 1.0)
    grid.set_obstacle(Point(1.5, 0.5))
    grid.set_obstacle(Point(0.5, 1.5))
    assert grid.world_to_grid(Point(-0.1, -0.1)) == (-1, -1)
    assert (1, 1) not in grid.get_neighbors(0, 0, diagonal=True)


def test_astar_returns_no_path_when_start_is_surrounded():
    grid = GridMap(3, 3, 1.0)
    for point in (Point(1.5, 0.5), Point(0.5, 1.5), Point(1.5, 1.5)):
        grid.set_obstacle(point)
    assert AStarPlanner(grid).plan(Point(0.5, 0.5), Point(2.5, 2.5)) is None


def test_path_follower_waits_for_odometry_and_stops_at_goal():
    node = _planner_node_class()()
    goal = PoseStamped()
    goal.pose.position.x = 1.0
    goal.pose.position.y = 0.0

    node._goal_callback(goal)
    assert node._current_path is None
    assert node._cmd_vel_pub.last_msg.linear.x == 0.0

    odom = Odometry()
    odom.pose.pose.orientation.w = 1.0
    node._odom_callback(odom)
    node._goal_callback(goal)
    assert node._current_path is None
    assert node._cmd_vel_pub.last_msg.linear.x == 0.0

    occupancy = OccupancyGrid()
    occupancy.info.width = 20
    occupancy.info.height = 20
    occupancy.info.resolution = 0.1
    occupancy.data = [0] * (occupancy.info.width * occupancy.info.height)
    node._map_callback(occupancy)
    assert node._current_path is not None

    node._follow_path()
    assert node._cmd_vel_pub.last_msg.linear.x >= 0.0

    for waypoint in node._current_path.waypoints[1:]:
        odom.pose.pose.position.x = waypoint.x
        odom.pose.pose.position.y = waypoint.y
        node._odom_callback(odom)
        node._follow_path()
        if node._current_path is None:
            break
    assert node._current_path is None
    assert node._cmd_vel_pub.last_msg.linear.x == 0.0


def test_unknown_occupancy_cells_are_not_traversable():
    node = _planner_node_class()()
    occupancy = OccupancyGrid()
    occupancy.info.width = 20
    occupancy.info.height = 20
    occupancy.info.resolution = 0.1
    occupancy.data = [0] * (occupancy.info.width * occupancy.info.height)
    occupancy.data[0] = -1
    node._map_callback(occupancy)
    assert node._grid_map.is_occupied(0, 0)


def test_occupancy_grid_geometry_is_used_for_obstacle_coordinates():
    node = _planner_node_class()()
    occupancy = OccupancyGrid()
    occupancy.info.width = 4
    occupancy.info.height = 3
    occupancy.info.resolution = 0.5
    occupancy.data = [0] * (occupancy.info.width * occupancy.info.height)
    occupancy.data[1] = 100
    node._map_callback(occupancy)
    assert node._grid_map.grid_width == 4
    assert node._grid_map.grid_height == 3
    assert node._grid_map.resolution == 0.5
    assert node._grid_map.is_occupied(1, 0)
