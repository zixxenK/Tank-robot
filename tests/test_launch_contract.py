"""Import and instantiate every maintained ROS launch description offline."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCH_FILES = sorted((ROOT / "host_ws" / "src").glob("*/launch/*.launch.py"))


def _load_launch(path: Path):
    module_name = "launch_contract_" + "_".join(path.parts[-3:]).replace(".", "_")
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_all_launch_files_generate_without_ros_runtime():
    assert LAUNCH_FILES, "No launch files were discovered"
    failures = []
    for path in LAUNCH_FILES:
        try:
            description = _load_launch(path).generate_launch_description()
            assert hasattr(description, "entities")
            assert description.entities
        except Exception as exc:  # noqa: BLE001 - report every broken launch
            failures.append(f"{path.relative_to(ROOT)}: {type(exc).__name__}: {exc}")
    assert not failures, "\n".join(failures)


def test_autonomous_stack_uses_production_odometry_topic():
    full_stack = (
        ROOT / "host_ws" / "src" / "robot_bringup" / "launch"
        / "full_stack.launch.py"
    ).read_text(encoding="utf-8")
    assert '"odom_topic": "/stm32/odom"' in full_stack
