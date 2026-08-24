"""Offline contracts for safe Rock64 startup and update behavior."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_startup_does_not_enable_optional_lidar_without_configuration():
    startup = _read("deployment/scripts/robot_start.sh")
    config = _read("deployment/systemd/systemd_config.conf.example")
    assert 'USE_LIDAR="${USE_LIDAR:-false}"' in startup
    assert "USE_LIDAR=false" in config


def test_periodic_self_update_never_flashes_firmware():
    updater = _read("deployment/scripts/self_update.sh")
    assert "NOT auto-flashing STM32" in updater
    assert "rock64_update_and_flash.sh" in updater


def test_pc_sync_preserves_machine_local_configuration():
    sync = _read("scripts/sync_rock64_safe.ps1")
    assert ".codex-preserved-systemd_config.conf" in sync
    assert "rm -rf '$RemoteRoot/deployment'" in sync


def test_robot_service_can_reach_startup_defaults_without_machine_config():
    service = _read("deployment/systemd/rock64-robot.service")
    startup = _read("deployment/scripts/robot_start.sh")
    assert "EnvironmentFile=-/opt/rock64-robot/deployment/systemd/" in service
    assert 'SERIAL_PORT="${SERIAL_PORT:-/dev/rock64_stm32}"' in startup


def test_all_active_build_paths_build_the_complete_canonical_workspace():
    """A newly added lab package must not be omitted by one build wrapper."""
    paths = (
        "scripts/unify_host_ws.sh",
        "scripts/e2e_mission.py",
        "scripts/sync_rock64_safe.ps1",
        "deployment/scripts/rebuild_workspace.sh",
        "deployment/scripts/rebuild_robot_bringup.sh",
        "deployment/scripts/rock64_update_and_flash.sh",
        "deployment/pc/setup_wsl_dashboard.sh",
    )
    for relative in paths:
        text = _read(relative)
        assert "colcon build --symlink-install" in text, relative
        assert "--packages-up-to" not in text, relative


def test_active_ros_build_wrappers_use_the_shared_environment_helper():
    paths = (
        "Makefile",
        "scripts/unify_host_ws.sh",
        "scripts/build_host_wsl.ps1",
        "scripts/e2e_mission.py",
        "scripts/sync_rock64_safe.ps1",
        "deployment/pc/setup_wsl_dashboard.sh",
        "deployment/pc/run_dashboard.sh",
        "deployment/pc/run_dashboard_remote.ps1",
        "deployment/scripts/rebuild_workspace.sh",
        "deployment/scripts/rebuild_robot_bringup.sh",
        "deployment/scripts/rock64_setup.sh",
        "deployment/scripts/rock64_update_and_flash.sh",
        "deployment/scripts/self_update.sh",
    )
    for relative in paths:
        text = _read(relative)
        assert "source_host_ws.sh" in text, relative


def test_active_docs_and_scripts_use_only_the_canonical_workspace_and_build():
    """Operator-facing paths must not resurrect the retired workspace split."""
    roots = (
        ROOT / "scripts",
        ROOT / "deployment",
        ROOT / "host_ws",
        ROOT / "docs",
    )
    excluded_parts = {
        "build",
        "install",
        "log",
        "_archive",
    }
    for base in roots:
        for path in base.rglob("*"):
            if (
                any(part in excluded_parts for part in path.parts)
                or path.suffix.lower() not in {".md", ".py", ".ps1", ".sh", ".yaml", ".yml", ".json"}
                or not path.is_file()
            ):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            assert "ros2_ws" not in text, path
            assert "--packages-select" not in text, path
            assert "--packages-up-to" not in text, path


def test_historical_setup_wrappers_resolve_the_repository_root():
    setup_wsl = _read("deployment/scripts/setup_wsl_gazebo.sh")
    assert 'REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"' in setup_wsl

    rebuild = _read("deployment/scripts/rebuild_workspace.sh")
    cleanup_index = rebuild.index("rm -rf build install log")
    source_index = rebuild.index("source \"${REPO_ROOT}/deployment/scripts/source_host_ws.sh\"")
    assert cleanup_index < source_index

    setup = _read("deployment/scripts/rock64_setup.sh")
    assert "cat > /dev/null <<'EOF'" not in setup
    assert "deployment/udev" in setup


def test_ps5_compatibility_aliases_are_derived_from_the_control_map():
    control_map = _read("host_ws/src/robot_control/robot_control/control_map.py")
    ps5 = _read("host_ws/src/robot_teleop/robot_teleop/ps5_ros_bridge.py")
    assert "DEFAULT_BUTTON_INDICES" in control_map
    assert 'BTN_CROSS = 0' not in ps5
    assert 'BTN_CROSS = DEFAULT_BUTTON_INDICES["cross"]' in ps5
    assert "BUTTON_NAMES = DEFAULT_BUTTON_NAMES" in ps5
    assert "self._apply_profile_axes(self._detected_profile)" in ps5
    assert "profile_defaults[\"throttle_axis\"]" in ps5


def test_control_map_validates_required_unique_button_indices():
    control_map = _read("host_ws/src/robot_control/robot_control/control_map.py")
    assert "REQUIRED_BUTTON_KEYS" in control_map
    assert "missing required button indices" in control_map
    assert "button_indices must not assign the same index twice" in control_map


def test_active_helpers_do_not_refer_to_removed_operator_documents():
    """Compatibility helpers must point at the current docs index."""
    paths = list((ROOT / "scripts").glob("*") ) + list(
        (ROOT / "deployment" / "scripts").glob("*")
    )
    for path in paths:
        if not path.is_file() or path.name == "source_host_ws.sh":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        assert "PC_TELEOP_SETUP.md" not in text, path
        assert "REMEDIATION_PLAN.md" not in text, path


def test_direct_motor_helpers_are_explicit_maintenance_paths():
    """Direct UART commands must not look like a normal drive interface."""
    paths = (
        "scripts/motor_command.py",
        "scripts/motor_direction.sh",
        "scripts/motor_forward.sh",
        "scripts/motor_back.sh",
        "scripts/motor_stop.sh",
        "scripts/motor_forward_reverse_test.py",
        "scripts/motor_start_stop_test.py",
        "scripts/motor_test_sequence.sh",
    )
    for relative in paths:
        assert "MAINTENANCE" in _read(relative), relative


def test_canonical_control_package_is_in_every_offline_import_path():
    makefile = _read("Makefile")
    runtime = _read("tests/test_runtime_imports.py")
    mission = _read("scripts/e2e_mission.py")
    assert "src/robot_control" in makefile
    assert '"robot_control"' in runtime
    assert "host_ws/src/robot_control/test" in mission


def test_local_environment_template_matches_the_active_stack():
    """The root template must not advertise retired providers or ROS defaults."""
    env = _read(".env.example")
    assert "LLM_PROVIDER" not in env
    assert "OPENAI_API_KEY" not in env
    assert "ANTHROPIC_API_KEY" not in env
    assert "OLLAMA_BASE_URL" not in env
    assert "VLLM_BASE_URL" not in env
    assert "ROS_DOMAIN_ID=42" in env
    assert "ROS_DISTRO=humble" in env
    assert "RMW_IMPLEMENTATION=rmw_fastrtps_cpp" in env
    assert "LM_STUDIO_BASE_URL" in env
    assert "LM_STUDIO_MODEL" in env
    assert "LM_API_TOKEN=" in env
    assert "HOST_WS_PATH=" in env


def test_runtime_templates_use_the_supported_explicit_ros_distro():
    config = _read("deployment/systemd/systemd_config.conf.example")
    guide = _read("deployment/docs/deployment_guide.md")
    assert "ROS_DISTRO=humble" in config
    assert "ROS_DISTRO=auto" not in config
    assert "ROS_DISTRO=humble" in guide
