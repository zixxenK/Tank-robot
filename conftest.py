"""Make the offline contract suite portable across pytest versions."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OFFLINE_IMPORT_ROOTS = [
    ROOT / "stubs",
    ROOT / "host_ws" / "src" / "agent_core",
    ROOT / "host_ws" / "src" / "robot_drivers",
    ROOT / "host_ws" / "src" / "robot_teleop",
    ROOT / "host_ws" / "src" / "robot_control",
    ROOT / "host_ws" / "src" / "robot_audio",
    ROOT / "host_ws" / "src" / "navigation",
    ROOT / "host_ws" / "src" / "perception",
    ROOT / "host_ws" / "src" / "telemetry_logger",
    ROOT / "host_ws" / "src" / "terrain_adaptation",
]

for _path in reversed(OFFLINE_IMPORT_ROOTS):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
