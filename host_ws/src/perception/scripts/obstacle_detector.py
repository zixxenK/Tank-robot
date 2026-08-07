#!/usr/bin/env python3
"""ROS2 node entry point for obstacle detection."""

import sys
from perception.obstacle_detector import main

if __name__ == "__main__":
    sys.exit(main() or 0)
