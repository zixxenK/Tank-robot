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
"""A* path planner implementation."""

import heapq
from typing import Tuple, Optional, Dict
from .path_planner import PathPlanner, Point, Path, GridMap


class AStarPlanner(PathPlanner):
    """A* path planner for grid-based navigation."""

    def __init__(self, grid_map: GridMap, diagonal: bool = True) -> None:
        """
        Initialize A* planner.

        Args:
            grid_map: Grid map for planning
            diagonal: Allow diagonal movements
        """
        super().__init__(grid_map)
        self._diagonal = diagonal

    def plan(self, start: Point, goal: Point) -> Optional[Path]:
        """
        Plan path from start to goal using A*.

        Args:
            start: Starting position
            goal: Goal position

        Returns:
            Path if found, None otherwise
        """
        # Convert to grid coordinates
        start_grid = self._grid_map.world_to_grid(start)
        goal_grid = self._grid_map.world_to_grid(goal)

        # Check if start or goal is occupied
        if self._grid_map.is_occupied(*start_grid):
            return None

        if self._grid_map.is_occupied(*goal_grid):
            return None

        # A* algorithm
        open_set = []
        heapq.heappush(open_set, (0, start_grid))

        came_from: Dict[Tuple[int, int], Tuple[int, int]] = {}
        g_score: Dict[Tuple[int, int], float] = {start_grid: 0.0}
        f_score: Dict[Tuple[int, int], float] = {start_grid: self.heuristic(start_grid, goal_grid)}

        while open_set:
            current = heapq.heappop(open_set)[1]

            if current == goal_grid:
                # Reconstruct path
                return self._reconstruct_path(came_from, current, start, goal)

            for neighbor in self._grid_map.get_neighbors(*current, diagonal=self._diagonal):
                # Calculate tentative g_score
                move_cost = 1.414 if self._is_diagonal(current, neighbor) else 1.0
                tentative_g = g_score[current] + move_cost

                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_score[neighbor] = tentative_g + self.heuristic(neighbor, goal_grid)
                    heapq.heappush(open_set, (f_score[neighbor], neighbor))

        # No path found
        return None

    def _is_diagonal(self, a: Tuple[int, int], b: Tuple[int, int]) -> bool:
        """Check if movement from a to b is diagonal."""
        return abs(a[0] - b[0]) == 1 and abs(a[1] - b[1]) == 1

    def _reconstruct_path(
        self,
        came_from: Dict[Tuple[int, int], Tuple[int, int]],
        current: Tuple[int, int],
        start: Point,
        goal: Point,
    ) -> Path:
        """Reconstruct path from came_from dictionary."""
        path = [current]
        total_cost = 0.0

        while current in came_from:
            prev = came_from[current]
            move_cost = 1.414 if self._is_diagonal(prev, current) else 1.0
            total_cost += move_cost
            current = prev
            path.append(current)

        path.reverse()

        # Convert to world coordinates
        waypoints = [self._grid_map.grid_to_world(*p) for p in path]

        return Path(waypoints=waypoints, cost=total_cost)

    def heuristic(self, a: Tuple[int, int], b: Tuple[int, int]) -> float:
        """Euclidean distance heuristic."""
        return super().heuristic(a, b)


class DijkstraPlanner(PathPlanner):
    """Dijkstra's algorithm (A* with zero heuristic)."""

    def __init__(self, grid_map: GridMap, diagonal: bool = True) -> None:
        """
        Initialize Dijkstra planner.

        Args:
            grid_map: Grid map for planning
            diagonal: Allow diagonal movements
        """
        super().__init__(grid_map)
        self._diagonal = diagonal

    def plan(self, start: Point, goal: Point) -> Optional[Path]:
        """
        Plan path from start to goal using Dijkstra.

        Args:
            start: Starting position
            goal: Goal position

        Returns:
            Path if found, None otherwise
        """
        # Convert to grid coordinates
        start_grid = self._grid_map.world_to_grid(start)
        goal_grid = self._grid_map.world_to_grid(goal)

        # Check if start or goal is occupied
        if self._grid_map.is_occupied(*start_grid):
            return None

        if self._grid_map.is_occupied(*goal_grid):
            return None

        # Dijkstra's algorithm (A* with h=0)
        open_set = []
        heapq.heappush(open_set, (0, start_grid))

        came_from: Dict[Tuple[int, int], Tuple[int, int]] = {}
        g_score: Dict[Tuple[int, int], float] = {start_grid: 0.0}

        while open_set:
            current = heapq.heappop(open_set)[1]

            if current == goal_grid:
                # Reconstruct path
                return self._reconstruct_path(came_from, current, start, goal)

            for neighbor in self._grid_map.get_neighbors(*current, diagonal=self._diagonal):
                move_cost = 1.414 if self._is_diagonal(current, neighbor) else 1.0
                tentative_g = g_score[current] + move_cost

                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    heapq.heappush(open_set, (g_score[neighbor], neighbor))

        # No path found
        return None

    def _is_diagonal(self, a: Tuple[int, int], b: Tuple[int, int]) -> bool:
        """Check if movement from a to b is diagonal."""
        return abs(a[0] - b[0]) == 1 and abs(a[1] - b[1]) == 1

    def _reconstruct_path(
        self,
        came_from: Dict[Tuple[int, int], Tuple[int, int]],
        current: Tuple[int, int],
        start: Point,
        goal: Point,
    ) -> Path:
        """Reconstruct path from came_from dictionary."""
        path = [current]
        total_cost = 0.0

        while current in came_from:
            prev = came_from[current]
            move_cost = 1.414 if self._is_diagonal(prev, current) else 1.0
            total_cost += move_cost
            current = prev
            path.append(current)

        path.reverse()

        # Convert to world coordinates
        waypoints = [self._grid_map.grid_to_world(*p) for p in path]

        return Path(waypoints=waypoints, cost=total_cost)
