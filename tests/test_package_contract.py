"""Ensure launch files only refer to executables installed by this workspace."""

from __future__ import annotations

import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "host_ws" / "src"
LOCAL_PACKAGES = {
    "agent_core",
    "navigation",
    "perception",
    "robot_audio",
    "robot_drivers",
    "robot_teleop",
    "terrain_adaptation",
}


def _installed_executables(package: str) -> set[str]:
    package_root = SOURCE_ROOT / package
    setup = package_root / "setup.py"
    if setup.exists():
        # Console-script names are the stable ROS executable contract.
        return set(
            re.findall(r"['\"]([A-Za-z0-9_]+)\s*=\s*", setup.read_text())
        )

    cmake = (package_root / "CMakeLists.txt").read_text()
    return set(re.findall(r"(?:scripts|telemetry_logger)/([^\s)]+\.py)", cmake))


def test_launch_nodes_use_installed_workspace_executables():
    installed = {
        package: _installed_executables(package) for package in LOCAL_PACKAGES
    }
    failures = []

    for launch_path in sorted(SOURCE_ROOT.glob("*/launch/*.launch.py")):
        tree = ast.parse(launch_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name) or node.func.id != "Node":
                continue
            keywords = {item.arg: item.value for item in node.keywords}
            package_node = keywords.get("package")
            executable_node = keywords.get("executable")
            if not (
                isinstance(package_node, ast.Constant)
                and isinstance(package_node.value, str)
                and isinstance(executable_node, ast.Constant)
                and isinstance(executable_node.value, str)
            ):
                continue
            package = package_node.value
            executable = executable_node.value
            if package in LOCAL_PACKAGES and executable not in installed[package]:
                failures.append(
                    f"{launch_path.relative_to(ROOT)}: "
                    f"{package}/{executable} is not installed"
                )

    assert not failures, "\n".join(failures)


def test_full_stack_owns_the_hardware_graph_and_has_a_no_terrain_command_path():
    launch = (SOURCE_ROOT / "robot_bringup" / "launch" / "full_stack.launch.py").read_text()
    teleop_setup = (SOURCE_ROOT / "robot_teleop" / "setup.py").read_text()
    assert "rock64_bringup.launch.py" in launch
    assert "cmd_vel_relay" in launch
    assert "cmd_vel_relay     = robot_teleop.cmd_vel_relay:main" in teleop_setup


def test_battery_display_range_matches_documented_pack_and_safety_thresholds():
    bridge = (
        SOURCE_ROOT / "robot_drivers" / "robot_drivers"
        / "stm32_hardened_bridge.py"
    ).read_text()
    safety = (
        SOURCE_ROOT / "agent_core" / "config" / "safety_gateway.yaml"
    ).read_text()
    assert 'battery_min_voltage", 9.5' in bridge
    assert 'battery_max_voltage", 12.6' in bridge
    assert "critical_battery_voltage: 9.5" in safety
    assert "minimum_battery_voltage: 10.5" in safety


def test_stm32_telemetry_snapshot_preserves_battery_presence_state():
    """A parsed battery frame must survive the ROS publication snapshot."""
    bridge = (
        SOURCE_ROOT / "robot_drivers" / "robot_drivers"
        / "stm32_hardened_bridge.py"
    ).read_text()
    assert "tel = replace(self._telemetry)" in bridge
    assert "if tel.battery_received:" in bridge
