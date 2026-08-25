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
"""IMU-based terrain classification using statistical features and machine learning."""

import numpy as np
from typing import Optional
from dataclasses import dataclass
from enum import Enum
from collections import deque


class TerrainType(Enum):
    """Terrain types for classification."""
    FLAT = "flat"
    UNEVEN = "uneven"
    SLOPE_UP = "slope_up"
    SLOPE_DOWN = "slope_down"
    OBSTACLE = "obstacle"
    UNKNOWN = "unknown"


@dataclass
class TerrainFeatures:
    """Statistical features extracted from IMU data."""
    accel_x_mean: float
    accel_x_std: float
    accel_y_mean: float
    accel_y_std: float
    accel_z_mean: float
    accel_z_std: float
    gyro_x_mean: float
    gyro_x_std: float
    gyro_y_mean: float
    gyro_y_std: float
    gyro_z_mean: float
    gyro_z_std: float
    accel_magnitude_mean: float
    accel_magnitude_std: float
    gyro_magnitude_mean: float
    gyro_magnitude_std: float


class TerrainClassifier:
    """IMU-based terrain classifier using statistical features."""

    def __init__(self, window_size: int = 100, sample_rate: float = 50.0) -> None:
        """
        Initialize terrain classifier.

        Args:
            window_size: Number of samples in analysis window
            sample_rate: IMU sample rate in Hz
        """
        self._window_size = window_size
        self._sample_rate = sample_rate

        # Data buffers
        self._accel_x = deque(maxlen=window_size)
        self._accel_y = deque(maxlen=window_size)
        self._accel_z = deque(maxlen=window_size)
        self._gyro_x = deque(maxlen=window_size)
        self._gyro_y = deque(maxlen=window_size)
        self._gyro_z = deque(maxlen=window_size)

        # Classification thresholds (tuned for typical tank robot)
        self._thresholds = {
            "flat_accel_std": 0.2,
            "flat_gyro_std": 0.1,
            "slope_accel_z_mean": 9.5,
            "uneven_accel_std": 0.5,
            "obstacle_accel_std": 1.0,
        }

    def add_imu_data(self, accel_x: float, accel_y: float, accel_z: float,
                     gyro_x: float, gyro_y: float, gyro_z: float) -> None:
        """Add IMU sample to buffer."""
        self._accel_x.append(accel_x)
        self._accel_y.append(accel_y)
        self._accel_z.append(accel_z)
        self._gyro_x.append(gyro_x)
        self._gyro_y.append(gyro_y)
        self._gyro_z.append(gyro_z)

    def extract_features(self) -> Optional[TerrainFeatures]:
        """Extract statistical features from current window."""
        if len(self._accel_x) < self._window_size:
            return None

        # Calculate statistics
        accel_x_arr = np.array(self._accel_x)
        accel_y_arr = np.array(self._accel_y)
        accel_z_arr = np.array(self._accel_z)
        gyro_x_arr = np.array(self._gyro_x)
        gyro_y_arr = np.array(self._gyro_y)
        gyro_z_arr = np.array(self._gyro_z)

        # Acceleration magnitude
        accel_mag = np.sqrt(accel_x_arr**2 + accel_y_arr**2 + accel_z_arr**2)
        gyro_mag = np.sqrt(gyro_x_arr**2 + gyro_y_arr**2 + gyro_z_arr**2)

        return TerrainFeatures(
            accel_x_mean=float(np.mean(accel_x_arr)),
            accel_x_std=float(np.std(accel_x_arr)),
            accel_y_mean=float(np.mean(accel_y_arr)),
            accel_y_std=float(np.std(accel_y_arr)),
            accel_z_mean=float(np.mean(accel_z_arr)),
            accel_z_std=float(np.std(accel_z_arr)),
            gyro_x_mean=float(np.mean(gyro_x_arr)),
            gyro_x_std=float(np.std(gyro_x_arr)),
            gyro_y_mean=float(np.mean(gyro_y_arr)),
            gyro_y_std=float(np.std(gyro_y_arr)),
            gyro_z_mean=float(np.mean(gyro_z_arr)),
            gyro_z_std=float(np.std(gyro_z_arr)),
            accel_magnitude_mean=float(np.mean(accel_mag)),
            accel_magnitude_std=float(np.std(accel_mag)),
            gyro_magnitude_mean=float(np.mean(gyro_mag)),
            gyro_magnitude_std=float(np.std(gyro_mag)),
        )

    def classify(self) -> TerrainType:
        """
        Classify terrain based on current IMU data.

        Returns:
            Detected terrain type
        """
        features = self.extract_features()
        if features is None:
            return TerrainType.UNKNOWN

        # Rule-based classification
        # Check for obstacle (high vibration)
        if features.accel_magnitude_std > self._thresholds["obstacle_accel_std"]:
            return TerrainType.OBSTACLE

        # Check for uneven terrain (moderate vibration)
        if features.accel_magnitude_std > self._thresholds["uneven_accel_std"]:
            return TerrainType.UNEVEN

        # Check for slope (acceleration z-axis deviation)
        if features.accel_z_mean < self._thresholds["slope_accel_z_mean"]:
            return TerrainType.SLOPE_UP
        elif features.accel_z_mean > 10.0:
            return TerrainType.SLOPE_DOWN

        # Default to flat terrain
        if features.accel_magnitude_std < self._thresholds["flat_accel_std"]:
            return TerrainType.FLAT

        return TerrainType.UNKNOWN

    def get_confidence(self) -> float:
        """
        Get confidence in current classification.

        Returns:
            Confidence score (0.0 to 1.0)
        """
        features = self.extract_features()
        if features is None:
            return 0.0

        # Confidence based on how far from decision boundaries
        terrain = self.classify()

        if terrain == TerrainType.OBSTACLE:
            # High confidence for obstacles
            return min(1.0, features.accel_magnitude_std / self._thresholds["obstacle_accel_std"])
        elif terrain == TerrainType.UNEVEN:
            return min(1.0, features.accel_magnitude_std / self._thresholds["uneven_accel_std"])
        elif terrain == TerrainType.FLAT:
            return 1.0 - (features.accel_magnitude_std / self._thresholds["flat_accel_std"])
        else:
            return 0.5

    def reset(self) -> None:
        """Clear all data buffers."""
        self._accel_x.clear()
        self._accel_y.clear()
        self._accel_z.clear()
        self._gyro_x.clear()
        self._gyro_y.clear()
        self._gyro_z.clear()

    def is_ready(self) -> bool:
        """Check if classifier has enough data."""
        return len(self._accel_x) >= self._window_size
