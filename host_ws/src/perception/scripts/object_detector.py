#!/usr/bin/env python3
"""ROS2 node entry point for object detection."""

import sys
from perception.object_detector import main

if __name__ == "__main__":
    sys.exit(main() or 0)
