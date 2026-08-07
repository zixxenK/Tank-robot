#!/usr/bin/env python3
"""Simple straight-line path planner for basic navigation."""

import numpy as np
from typing import Optional
from .path_planner import PathPlanner, Point, Path, GridMap


class SimplePlanner(PathPlanner):
    """Simple straight-line planner with obstacle avoidance."""

    def __init__(self, grid_map: GridMap, look_ahead: float = 0.5) -> None:
        """
        Initialize simple planner.

        Args:
            grid_map: Grid map for planning
            look_ahead: Look-ahead distance for obstacle checking
        """
        super().__init__(grid_map)
        self._look_ahead = look_ahead

    def plan(self, start: Point, goal: Point) -> Optional[Path]:
        """
        Plan straight-line path from start to goal.

        Args:
            start: Starting position
            goal: Goal position

        Returns:
            Path if clear, None if obstacles detected
        """
        # Check if path is clear
        if self._is_path_clear(start, goal):
            # Return direct path
            return Path(waypoints=[start, goal], cost=start.distance_to(goal))

        # Try to find a waypoint around obstacles
        waypoint = self._find_waypoint(start, goal)
        if waypoint:
            return Path(waypoints=[start, waypoint, goal], cost=start.distance_to(waypoint) + waypoint.distance_to(goal))

        return None

    def _is_path_clear(self, start: Point, goal: Point, step_size: float = 0.1) -> bool:
        """
        Check if straight-line path is clear of obstacles.

        Args:
            start: Starting position
            goal: Goal position
            step_size: Step size for checking

        Returns:
            True if path is clear, False otherwise
        """
        direction = goal - start
        distance = start.distance_to(goal)
        num_steps = int(distance / step_size)

        for i in range(num_steps + 1):
            t = i / num_steps if num_steps > 0 else 0
            point = Point(
                start.x + t * direction.x,
                start.y + t * direction.y,
            )

            grid_x, grid_y = self._grid_map.world_to_grid(point)
            if self._grid_map.is_occupied(grid_x, grid_y):
                return False

        return True

    def _find_waypoint(self, start: Point, goal: Point) -> Optional[Point]:
        """
        Find a waypoint to navigate around obstacles.

        Args:
            start: Starting position
            goal: Goal position

        Returns:
            Waypoint if found, None otherwise
        """
        # Try perpendicular offsets
        direction = goal - start
        perp = Point(-direction.y, direction.x)
        perp_length = perp.distance_to(Point(0, 0))
        
        if perp_length > 0:
            perp = Point(perp.x / perp_length, perp.y / perp_length)

        # Try different offsets
        offsets = [0.5, 1.0, 1.5, 2.0]
        
        for offset in offsets:
            # Try left offset
            waypoint_left = Point(
                start.x + offset * perp.x,
                start.y + offset * perp.y,
            )
            if self._is_path_clear(start, waypoint_left) and self._is_path_clear(waypoint_left, goal):
                return waypoint_left

            # Try right offset
            waypoint_right = Point(
                start.x - offset * perp.x,
                start.y - offset * perp.y,
            )
            if self._is_path_clear(start, waypoint_right) and self._is_path_clear(waypoint_right, goal):
                return waypoint_right

        return None
