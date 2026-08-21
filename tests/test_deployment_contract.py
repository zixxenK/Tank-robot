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
