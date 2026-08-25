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
"""Adaptive controller that adjusts robot behavior based on terrain classification."""

from __future__ import annotations

import numpy as np
from typing import Dict
from dataclasses import dataclass
from .terrain_classifier import TerrainClassifier, TerrainType


@dataclass
class ControlParameters:
    """Control parameters for different terrain types."""
    max_linear_speed: float
    max_angular_speed: float
    acceleration_limit: float
    deceleration_limit: float
    motor_power: float  # 0.0 to 1.0


class AdaptiveController:
    """Adaptive controller that adjusts control parameters based on terrain."""

    def __init__(self, terrain_classifier: TerrainClassifier) -> None:
        """
        Initialize adaptive controller.

        Args:
            terrain_classifier: Terrain classifier instance
        """
        self._terrain_classifier = terrain_classifier

        # Default control parameters for each terrain type
        self._terrain_params: Dict[TerrainType, ControlParameters] = {
            TerrainType.FLAT: ControlParameters(
                max_linear_speed=1.0,
                max_angular_speed=1.5,
                acceleration_limit=2.0,
                deceleration_limit=2.0,
                motor_power=0.8,
            ),
            TerrainType.UNEVEN: ControlParameters(
                max_linear_speed=0.5,
                max_angular_speed=1.0,
                acceleration_limit=1.0,
                deceleration_limit=1.5,
                motor_power=0.6,
            ),
            TerrainType.SLOPE_UP: ControlParameters(
                max_linear_speed=0.7,
                max_angular_speed=1.0,
                acceleration_limit=1.5,
                deceleration_limit=1.5,
                motor_power=0.9,  # More power for climbing
            ),
            TerrainType.SLOPE_DOWN: ControlParameters(
                max_linear_speed=0.6,
                max_angular_speed=1.0,
                acceleration_limit=1.0,
                deceleration_limit=2.0,  # More braking for descent
                motor_power=0.4,
            ),
            TerrainType.OBSTACLE: ControlParameters(
                max_linear_speed=0.2,
                max_angular_speed=0.5,
                acceleration_limit=0.5,
                deceleration_limit=2.0,
                motor_power=0.5,
            ),
            TerrainType.UNKNOWN: ControlParameters(
                max_linear_speed=0.5,
                max_angular_speed=0.8,
                acceleration_limit=1.0,
                deceleration_limit=1.5,
                motor_power=0.6,
            ),
        }

        # Current parameters
        self._current_params = self._terrain_params[TerrainType.UNKNOWN]
        self._current_terrain = TerrainType.UNKNOWN

    def update(self, accel_x: float, accel_y: float, accel_z: float,
               gyro_x: float, gyro_y: float, gyro_z: float) -> None:
        """
        Update terrain classification and control parameters.

        Args:
            accel_x: Acceleration x (m/s^2)
            accel_y: Acceleration y (m/s^2)
            accel_z: Acceleration z (m/s^2)
            gyro_x: Angular velocity x (rad/s)
            gyro_y: Angular velocity y (rad/s)
            gyro_z: Angular velocity z (rad/s)
        """
        # Add IMU data to classifier
        self._terrain_classifier.add_imu_data(
            accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z
        )

        # Classify terrain
        if self._terrain_classifier.is_ready():
            terrain = self._terrain_classifier.classify()
            confidence = self._terrain_classifier.get_confidence()

            # Update parameters if confidence is high enough
            if confidence > 0.6:
                self._current_terrain = terrain
                self._current_params = self._terrain_params[terrain]

    def get_current_parameters(self) -> ControlParameters:
        """Get current control parameters."""
        return self._current_params

    def get_current_terrain(self) -> TerrainType:
        """Get current terrain classification."""
        return self._current_terrain

    def adapt_command(self, linear_x: float, angular_z: float) -> tuple[float, float]:
        """
        Adapt velocity command based on current terrain.

        Args:
            linear_x: Desired linear velocity (m/s)
            angular_z: Desired angular velocity (rad/s)

        Returns:
            Adapted (linear_x, angular_z) tuple
        """
        # Clamp to terrain-specific limits
        adapted_linear = np.clip(
            linear_x,
            -self._current_params.max_linear_speed,
            self._current_params.max_linear_speed
        )
        adapted_angular = np.clip(
            angular_z,
            -self._current_params.max_angular_speed,
            self._current_params.max_angular_speed
        )

        # Apply power scaling
        adapted_linear *= self._current_params.motor_power

        return adapted_linear, adapted_angular

    def get_motor_power(self) -> float:
        """Get current motor power setting."""
        return self._current_params.motor_power

    def get_acceleration_limit(self) -> float:
        """Get current acceleration limit."""
        return self._current_params.acceleration_limit

    def get_deceleration_limit(self) -> float:
        """Get current deceleration limit."""
        return self._current_params.deceleration_limit

    def set_terrain_parameters(self, terrain: TerrainType, params: ControlParameters) -> None:
        """
        Set custom parameters for a terrain type.

        Args:
            terrain: Terrain type
            params: Control parameters
        """
        self._terrain_params[terrain] = params

    def reset(self) -> None:
        """Reset controller to default state."""
        self._terrain_classifier.reset()
        self._current_params = self._terrain_params[TerrainType.UNKNOWN]
        self._current_terrain = TerrainType.UNKNOWN
