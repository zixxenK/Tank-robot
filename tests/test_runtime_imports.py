"""Import every packaged Python runtime module with the offline ROS shims."""

from __future__ import annotations

import importlib
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
PACKAGES = (
    "agent_core",
    "robot_drivers",
    "robot_teleop",
    "robot_control",
    "robot_audio",
    "navigation",
    "perception",
    "telemetry_logger",
    "terrain_adaptation",
)

# Keep this contract test runnable even when the caller only put ``stubs`` on
# PYTHONPATH.  Each ament Python package is source-rooted one level below its
# package directory in this repository.
for _package in PACKAGES:
    _source_root = ROOT / "host_ws" / "src" / _package
    if str(_source_root) not in sys.path:
        sys.path.insert(0, str(_source_root))


def test_packaged_runtime_modules_import_offline():
    failures = []
    for package in PACKAGES:
        package_root = ROOT / "host_ws" / "src" / package / package
        for path in sorted(package_root.rglob("*.py")):
            if path.name == "__init__.py" or "__pycache__" in path.parts:
                continue
            relative = path.relative_to(package_root).with_suffix("")
            module_name = f"{package}." + ".".join(relative.parts)
            try:
                importlib.import_module(module_name)
            except Exception as exc:  # noqa: BLE001 - report every failure
                failures.append(
                    f"{module_name}: {type(exc).__name__}: {exc}"
                )

    assert not failures, "\n".join(failures)
