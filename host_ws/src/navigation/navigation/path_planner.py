#!/usr/bin/env python3
"""Base path planner interface and utilities."""

import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import heapq
import math


class PlannerType(Enum):
    """Types of path planners."""
    ASTAR = "astar"
    DIJKSTRA = "dijkstra"
    SIMPLE = "simple"
    LEARNED = "learned"


@dataclass
class Point:
    """2D point with coordinates."""
    x: float
    y: float

    def distance_to(self, other: 'Point') -> float:
        """Euclidean distance to another point."""
        return np.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)

    def __add__(self, other: 'Point') -> 'Point':
        return Point(self.x + other.x, self.y + other.y)

    def __sub__(self, other: 'Point') -> 'Point':
        return Point(self.x - other.x, self.y - other.y)


@dataclass
class Path:
    """Path consisting of waypoints."""
    waypoints: List[Point]
    cost: float = 0.0

    def __len__(self) -> int:
        return len(self.waypoints)

    def is_empty(self) -> bool:
        return len(self.waypoints) == 0


@dataclass
class Obstacle:
    """Obstacle representation."""
    center: Point
    radius: float
    type: str = "static"  # static, dynamic


class GridMap:
    """2D grid map for path planning."""

    def __init__(self, width: int, height: int, resolution: float = 0.1) -> None:
        """
        Initialize grid map.

        Args:
            width: Width in meters
            height: Height in meters
            resolution: Grid cell size in meters
        """
        if width <= 0 or height <= 0 or resolution <= 0:
            raise ValueError("grid dimensions and resolution must be positive")
        self._width = float(width)
        self._height = float(height)
        self._resolution = float(resolution)
        self._grid_width = int(width / resolution)
        self._grid_height = int(height / resolution)
        self._grid = np.zeros((self._grid_height, self._grid_width), dtype=np.uint8)
        self._obstacles: List[Obstacle] = []
        self._origin = Point(0.0, 0.0)

    @property
    def resolution(self) -> float:
        """Return the cell resolution in metres."""
        return self._resolution

    @property
    def grid_width(self) -> int:
        """Return the number of horizontal cells in the map."""
        return self._grid_width

    @property
    def grid_height(self) -> int:
        """Return the number of vertical cells in the map."""
        return self._grid_height

    def reconfigure_from_occupancy_grid(
        self,
        width: int,
        height: int,
        resolution: float,
    ) -> None:
        """Match the grid exactly to a ROS OccupancyGrid geometry.

        The previous planner kept its startup-sized grid even after receiving
        a map with different dimensions or resolution. That made obstacle
        coordinates inconsistent with ``world_to_grid`` and could silently
        plan through occupied cells.
        """
        width = int(width)
        height = int(height)
        resolution = float(resolution)
        if width <= 0 or height <= 0 or not math.isfinite(resolution):
            raise ValueError("occupancy grid geometry must be finite and positive")
        if resolution <= 0.0:
            raise ValueError("occupancy grid resolution must be positive")

        self._resolution = resolution
        self._grid_width = width
        self._grid_height = height
        self._width = width * resolution
        self._height = height * resolution
        self._grid = np.zeros((height, width), dtype=np.uint8)
        self._obstacles.clear()

    def set_origin(self, origin: Point) -> None:
        """Set the world coordinate of the grid's lower-left corner."""
        self._origin = Point(float(origin.x), float(origin.y))

    def world_to_grid(self, point: Point) -> Tuple[int, int]:
        """Convert world coordinates to grid coordinates."""
        grid_x = math.floor((point.x - self._origin.x) / self._resolution)
        grid_y = math.floor((point.y - self._origin.y) / self._resolution)
        return grid_x, grid_y

    def grid_to_world(self, grid_x: int, grid_y: int) -> Point:
        """Convert grid coordinates to world coordinates."""
        x = self._origin.x + (grid_x + 0.5) * self._resolution
        y = self._origin.y + (grid_y + 0.5) * self._resolution
        return Point(x, y)

    def is_occupied(self, grid_x: int, grid_y: int) -> bool:
        """Check if grid cell is occupied."""
        if not (0 <= grid_x < self._grid_width and 0 <= grid_y < self._grid_height):
            return True  # Out of bounds is considered occupied
        return self._grid[grid_y, grid_x] == 1

    def set_obstacle(self, point: Point, radius: float = 0.0) -> None:
        """Mark obstacle on grid."""
        if radius > 0:
            # Mark circular obstacle
            grid_x, grid_y = self.world_to_grid(point)
            grid_radius = int(radius / self._resolution)
            
            for dy in range(-grid_radius, grid_radius + 1):
                for dx in range(-grid_radius, grid_radius + 1):
                    if dx*dx + dy*dy <= grid_radius*grid_radius:
                        gx, gy = grid_x + dx, grid_y + dy
                        if 0 <= gx < self._grid_width and 0 <= gy < self._grid_height:
                            self._grid[gy, gx] = 1
        else:
            # Mark single cell
            grid_x, grid_y = self.world_to_grid(point)
            if 0 <= grid_x < self._grid_width and 0 <= grid_y < self._grid_height:
                self._grid[grid_y, grid_x] = 1

    def clear_obstacle(self, point: Point) -> None:
        """Clear obstacle at point."""
        grid_x, grid_y = self.world_to_grid(point)
        if 0 <= grid_x < self._grid_width and 0 <= grid_y < self._grid_height:
            self._grid[grid_y, grid_x] = 0

    def clear_all(self) -> None:
        """Clear all obstacles."""
        self._grid.fill(0)
        self._obstacles.clear()

    def get_neighbors(self, grid_x: int, grid_y: int, diagonal: bool = True) -> List[Tuple[int, int]]:
        """Get valid neighboring cells."""
        neighbors = []
        
        # 4-connected neighbors
        directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]
        
        if diagonal:
            # Add 8-connected neighbors
            directions.extend([(1, 1), (1, -1), (-1, 1), (-1, -1)])
        
        for dx, dy in directions:
            nx, ny = grid_x + dx, grid_y + dy
            if 0 <= nx < self._grid_width and 0 <= ny < self._grid_height:
                # Do not cut diagonally through two touching obstacles.
                diagonal_blocked = (
                    dx != 0
                    and dy != 0
                    and (
                        self.is_occupied(grid_x + dx, grid_y)
                        or self.is_occupied(grid_x, grid_y + dy)
                    )
                )
                if not diagonal_blocked and not self.is_occupied(nx, ny):
                    neighbors.append((nx, ny))
        
        return neighbors


class PathPlanner:
    """Base class for path planners."""

    def __init__(self, grid_map: GridMap) -> None:
        """Initialize planner with grid map."""
        self._grid_map = grid_map

    def plan(self, start: Point, goal: Point) -> Optional[Path]:
        """
        Plan path from start to goal.

        Args:
            start: Starting position
            goal: Goal position

        Returns:
            Path if found, None otherwise
        """
        raise NotImplementedError("Subclasses must implement plan()")

    def heuristic(self, a: Tuple[int, int], b: Tuple[int, int]) -> float:
        """Heuristic function for A* (Euclidean distance)."""
        return np.sqrt((a[0] - b[0])**2 + (a[1] - b[1])**2)

    def smooth_path(self, path: Path, iterations: int = 10) -> Path:
        """Smooth path using simple averaging."""
        if len(path.waypoints) < 3:
            return path

        smoothed = path.waypoints.copy()
        for _ in range(iterations):
            for i in range(1, len(smoothed) - 1):
                smoothed[i] = Point(
                    (smoothed[i-1].x + smoothed[i].x + smoothed[i+1].x) / 3,
                    (smoothed[i-1].y + smoothed[i].y + smoothed[i+1].y) / 3,
                )

        return Path(waypoints=smoothed, cost=path.cost)

    def interpolate_path(self, path: Path, max_distance: float = 0.2) -> Path:
        """Interpolate waypoints to ensure max distance between them."""
        if len(path.waypoints) < 2:
            return path

        interpolated = [path.waypoints[0]]
        
        for i in range(1, len(path.waypoints)):
            prev = interpolated[-1]
            curr = path.waypoints[i]
            distance = prev.distance_to(curr)
            
            if distance > max_distance:
                num_points = int(distance / max_distance)
                for j in range(1, num_points + 1):
                    t = j / (num_points + 1)
                    new_point = Point(
                        prev.x + t * (curr.x - prev.x),
                        prev.y + t * (curr.y - prev.y),
                    )
                    interpolated.append(new_point)
            
            interpolated.append(curr)

        return Path(waypoints=interpolated, cost=path.cost)
