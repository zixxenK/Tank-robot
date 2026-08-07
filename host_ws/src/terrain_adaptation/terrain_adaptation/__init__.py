"""Terrain adaptation package for IMU-based terrain classification and adaptive control."""

from .terrain_classifier import TerrainClassifier
from .adaptive_controller import AdaptiveController

__all__ = ['TerrainClassifier', 'AdaptiveController']
