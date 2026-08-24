"""Import and instantiate every maintained ROS launch description offline."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import re


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


def test_full_stack_defaults_to_drive_and_cameras_only():
    """Future autonomy and accessory launch paths require explicit opt-in."""
    full_stack = (
        ROOT / "host_ws" / "src" / "robot_bringup" / "launch"
        / "full_stack.launch.py"
    ).read_text(encoding="utf-8")
    for argument in ("use_perception", "use_navigation", "use_terrain_adaptation"):
        match = re.search(
            rf'DeclareLaunchArgument\(\s*"{argument}".*?default_value="([^"]+)"',
            full_stack,
            re.DOTALL,
        )
        assert match and match.group(1) == "false", argument
    assert '"use_camera"' in full_stack
    assert 'default_value="true"' in full_stack


def test_full_stack_propagates_the_canonical_control_map() -> None:
    """Nested hardware bringup must receive the same control-map path."""
    full_stack = (
        ROOT / "host_ws" / "src" / "robot_bringup" / "launch"
        / "full_stack.launch.py"
    ).read_text(encoding="utf-8")
    assert '"control_map"' in full_stack
    assert 'FindPackageShare("robot_control")' in full_stack
    assert '"control_map": LaunchConfiguration("control_map")' in full_stack


def test_production_autonomy_launches_never_target_operator_cmd_vel():
    """Autonomous nodes use proposal topics; /cmd_vel remains operator-owned."""
    launch_paths = (
        ROOT / "host_ws" / "src" / "robot_bringup" / "launch" / "full_stack.launch.py",
        ROOT / "host_ws" / "src" / "navigation" / "launch" / "navigation.launch.py",
        ROOT / "host_ws" / "src" / "terrain_adaptation" / "launch" / "terrain_adaptation.launch.py",
    )
    for path in launch_paths:
        text = path.read_text(encoding="utf-8")
        assert '"cmd_vel_topic": "/cmd_vel"' not in text
        assert "'cmd_vel_topic': '/cmd_vel'" not in text
        assert '"cmd_vel_input": "/cmd_vel"' not in text
        assert "'cmd_vel_input': '/cmd_vel'" not in text
    assert "/agent/cmd_vel_proposed" in launch_paths[0].read_text(encoding="utf-8")


def test_audio_launch_and_waypoint_trigger_use_canonical_stm32_odom():
    launch = (
        ROOT / "host_ws" / "src" / "robot_audio" / "launch"
        / "robot_audio.launch.py"
    ).read_text(encoding="utf-8")
    trigger = (
        ROOT / "host_ws" / "src" / "robot_audio" / "robot_audio"
        / "waypoint_music_trigger.py"
    ).read_text(encoding="utf-8")
    assert "default_value='/stm32/odom'" in launch
    assert "'odom_topic': LaunchConfiguration('odom_topic')" in launch
    assert "self.declare_parameter('odom_topic', '/stm32/odom')" in trigger


def test_local_launch_include_targets_exist_in_the_source_tree():
    """Compatibility aliases cannot silently reference removed launch files."""
    bringup_launch_dir = ROOT / "host_ws" / "src" / "robot_bringup" / "launch"
    for name in (
        "rock64_bringup.launch.py",
        "pc_dashboard.launch.py",
        "gazebo_telemetry.launch.py",
    ):
        assert (bringup_launch_dir / name).is_file(), name
    alias = (bringup_launch_dir / "rock64_dashboard.launch.py").read_text(
        encoding="utf-8"
    )
    assert '"pc_dashboard.launch.py"' in alias
