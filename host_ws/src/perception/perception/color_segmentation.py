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
"""Color segmentation for object detection and tracking.

Provides HSV-based color segmentation with adaptive thresholding
and morphological operations for robust object detection.
"""

import cv2
import numpy as np
from typing import Tuple, List, Optional, Dict
from dataclasses import dataclass


@dataclass
class ColorRange:
    """HSV color range for segmentation."""
    name: str
    lower_hsv: Tuple[int, int, int]
    upper_hsv: Tuple[int, int, int]
    min_area: int = 500
    max_area: int = 50000


class ColorSegmentation:
    """HSV-based color segmentation for object detection."""

    def __init__(self) -> None:
        """Initialize color segmentation with default color ranges."""
        self._color_ranges: Dict[str, ColorRange] = {
            "red": ColorRange(
                name="red",
                lower_hsv=(0, 100, 100),
                upper_hsv=(10, 255, 255),
                min_area=500,
                max_area=50000,
            ),
            "green": ColorRange(
                name="green",
                lower_hsv=(40, 50, 50),
                upper_hsv=(80, 255, 255),
                min_area=500,
                max_area=50000,
            ),
            "blue": ColorRange(
                name="blue",
                lower_hsv=(100, 100, 100),
                upper_hsv=(130, 255, 255),
                min_area=500,
                max_area=50000,
            ),
            "yellow": ColorRange(
                name="yellow",
                lower_hsv=(20, 100, 100),
                upper_hsv=(30, 255, 255),
                min_area=500,
                max_area=50000,
            ),
            "orange": ColorRange(
                name="orange",
                lower_hsv=(10, 100, 100),
                upper_hsv=(20, 255, 255),
                min_area=500,
                max_area=50000,
            ),
            "purple": ColorRange(
                name="purple",
                lower_hsv=(130, 50, 50),
                upper_hsv=(160, 255, 255),
                min_area=500,
                max_area=50000,
            ),
        }

    def add_color_range(self, color_range: ColorRange) -> None:
        """Add a custom color range."""
        self._color_ranges[color_range.name] = color_range

    def remove_color_range(self, name: str) -> None:
        """Remove a color range."""
        if name in self._color_ranges:
            del self._color_ranges[name]

    def get_color_range(self, name: str) -> Optional[ColorRange]:
        """Get a color range by name."""
        return self._color_ranges.get(name)

    def segment_color(
        self,
        image: np.ndarray,
        color_name: str,
        morph_open: bool = True,
        morph_close: bool = True,
    ) -> np.ndarray:
        """
        Segment a specific color from the image.

        Args:
            image: Input BGR image
            color_name: Name of color to segment
            morph_open: Apply morphological opening
            morph_close: Apply morphological closing

        Returns:
            Binary mask of segmented color
        """
        if color_name not in self._color_ranges:
            raise ValueError(f"Color '{color_name}' not found")

        color_range = self._color_ranges[color_name]
        hsv_image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        lower = np.array(color_range.lower_hsv)
        upper = np.array(color_range.upper_hsv)

        # Handle red color (wraps around in HSV)
        if color_name == "red":
            mask1 = cv2.inRange(hsv_image, lower, upper)
            lower2 = np.array([170, 100, 100])
            upper2 = np.array([180, 255, 255])
            mask2 = cv2.inRange(hsv_image, lower2, upper2)
            mask = cv2.bitwise_or(mask1, mask2)
        else:
            mask = cv2.inRange(hsv_image, lower, upper)

        # Morphological operations
        if morph_open or morph_close:
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

            if morph_open:
                mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

            if morph_close:
                mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        return mask

    def find_contours(
        self,
        mask: np.ndarray,
        min_area: Optional[int] = None,
        max_area: Optional[int] = None,
    ) -> List[np.ndarray]:
        """
        Find contours in a binary mask.

        Args:
            mask: Binary mask
            min_area: Minimum contour area
            max_area: Maximum contour area

        Returns:
            List of contours
        """
        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        filtered_contours = []
        for contour in contours:
            area = cv2.contourArea(contour)

            if min_area is not None and area < min_area:
                continue
            if max_area is not None and area > max_area:
                continue

            filtered_contours.append(contour)

        return filtered_contours

    def detect_objects(
        self,
        image: np.ndarray,
        color_name: str,
        return_contours: bool = False,
    ) -> List[Tuple[Tuple[int, int, int, int], float, Optional[np.ndarray]]]:
        """
        Detect objects of a specific color.

        Args:
            image: Input BGR image
            color_name: Name of color to detect
            return_contours: Return contour points

        Returns:
            List of (bbox, area, contour) tuples
        """
        mask = self.segment_color(image, color_name)
        color_range = self._color_ranges[color_name]

        contours = self.find_contours(
            mask,
            min_area=color_range.min_area,
            max_area=color_range.max_area,
        )

        results = []
        for contour in contours:
            area = cv2.contourArea(contour)
            x, y, w, h = cv2.boundingRect(contour)

            contour_data = contour if return_contours else None
            results.append(((x, y, w, h), area, contour_data))

        return results

    def detect_all_colors(
        self,
        image: np.ndarray,
        return_contours: bool = False,
    ) -> Dict[str, List[Tuple[Tuple[int, int, int, int], float]]]:
        """
        Detect objects of all configured colors.

        Args:
            image: Input BGR image
            return_contours: Return contour points

        Returns:
            Dictionary mapping color names to detection results
        """
        results = {}

        for color_name in self._color_ranges:
            detections = self.detect_objects(image, color_name, return_contours)
            results[color_name] = detections

        return results

    def adaptive_segment(
        self,
        image: np.ndarray,
        color_name: str,
        adaptive_method: int = cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        block_size: int = 11,
        C: int = 2,
    ) -> np.ndarray:
        """
        Adaptive thresholding for varying lighting conditions.

        Args:
            image: Input BGR image
            color_name: Name of color to segment
            adaptive_method: Adaptive thresholding method
            block_size: Size of neighborhood for adaptive thresholding
            C: Constant subtracted from mean

        Returns:
            Binary mask
        """
        # Get initial color segmentation
        mask = self.segment_color(image, color_name, morph_open=False, morph_close=False)

        # Convert to grayscale for adaptive thresholding
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Apply adaptive thresholding
        adaptive_mask = cv2.adaptiveThreshold(
            gray,
            255,
            adaptive_method,
            cv2.THRESH_BINARY,
            block_size,
            C,
        )

        # Combine with color mask
        combined = cv2.bitwise_and(mask, adaptive_mask)

        # Apply morphological operations
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        combined = cv2.morphologyEx(combined, cv2.MORPH_OPEN, kernel)
        combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel)

        return combined

    def track_object(
        self,
        image: np.ndarray,
        color_name: str,
        tracker_type: str = "CSRT",
    ) -> Optional[Tuple[int, int, int, int]]:
        """
        Track an object of a specific color.

        Args:
            image: Input BGR image
            color_name: Name of color to track
            tracker_type: OpenCV tracker type

        Returns:
            Bounding box (x, y, w, h) or None if not found
        """
        detections = self.detect_objects(image, color_name)

        if not detections:
            return None

        # Return the largest detection
        detections.sort(key=lambda x: x[1], reverse=True)
        return detections[0][0]

    def visualize_segmentation(
        self,
        image: np.ndarray,
        mask: np.ndarray,
        color: Tuple[int, int, int] = (0, 255, 0),
    ) -> np.ndarray:
        """
        Visualize segmentation mask overlay on image.

        Args:
            image: Input BGR image
            mask: Binary mask
            color: BGR color for overlay

        Returns:
            Image with mask overlay
        """
        # Create colored mask
        colored_mask = np.zeros_like(image)
        colored_mask[mask > 0] = color

        # Blend with original image
        result = cv2.addWeighted(image, 0.7, colored_mask, 0.3, 0)

        return result
