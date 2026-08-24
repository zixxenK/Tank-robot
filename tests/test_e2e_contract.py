"""Contracts for the human-first one-shot E2E runner."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_root_e2e_wrappers_take_no_operator_parameters():
    bash = _read("run_e2e.sh")
    powershell = _read("run_e2e.ps1")
    assert "e2e_mission.py" in bash
    assert "e2e_mission.py" in powershell
    assert "$@" not in bash
    assert "param(" not in powershell.lower()


def test_makefile_exposes_e2e_as_the_primary_operator_target():
    makefile = _read("Makefile")
    assert "e2e:" in makefile
    assert "Run complete one-shot E2E mission" in makefile
    assert "scripts/e2e_mission.py" in makefile


def test_e2e_runner_captures_logs_and_uses_safe_hardware_defaults():
    runner = _read("scripts/e2e_mission.py")
    assert "stdout=subprocess.PIPE" in runner
    assert "stderr=subprocess.PIPE" in runner
    assert '"hardware_acceptance.sh")]' in runner
    assert "--tracks-raised" not in runner
    assert "=== TANK-ROBOT SYSTEM REPORT ===" in runner
    assert "[ SUBSYSTEMS ]:" in runner


def test_basic_acceptance_keeps_ps5_informational_and_excludes_accessories():
    runner = _read(
        "host_ws/src/robot_drivers/robot_drivers/hardware_test_runner.py"
    )
    acceptance = _read("scripts/hardware_acceptance.sh")
    launch = _read(
        "host_ws/src/robot_bringup/launch/hardware_acceptance.launch.py"
    )

    assert '"STM32 onboard IMU", self._test_imu' in runner
    assert '"PS5 controller",\n                SKIP,\n                False' in runner
    assert "_test_ps5" not in runner
    assert "Hiwonder Glowy ultrasonic" not in runner
    assert "STL-50B2 LiDAR" not in runner
    assert "SG90 servo" not in runner
    assert "--no-imu" not in acceptance
    assert "--with-lidar" not in acceptance
    assert '"use_lidar": "false"' in launch
    assert '"use_ultrasonic": "false"' in launch


def test_failure_summary_patterns_are_valid_and_plain():
    import importlib.util
    import sys

    path = ROOT / "scripts" / "e2e_mission.py"
    spec = importlib.util.spec_from_file_location("e2e_mission_contract", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    summary = module._plain_failure(
        "Traceback details\nCMake Error at firmware.cmake: bad pin\nmore",
        1,
    )
    assert "CMake Error" in summary
    assert "\n" not in summary
    assert "Traceback" not in summary

    pytest_summary = module._plain_failure(
        "ERROR collecting test_example.py\nTraceback:\n"
        "E   ImportError: cannot import name 'TypeAlias'\n",
        1,
    )
    assert "ImportError" in pytest_summary
    assert "Traceback" not in pytest_summary


def test_pc_stm32_flashing_is_disabled_and_delegated_to_rock64():
    windows_flash = _read("scripts/flash_stm32_windows.ps1")
    unix_flash = _read("scripts/flash_stm32.sh")
    makefile = _read("Makefile")
    source_of_truth = _read("docs/SOURCE_OF_TRUTH_1_0.md")

    assert "Direct STM32 flashing from a PC is disabled" in windows_flash
    assert "openocd.exe" not in windows_flash.lower()
    assert '[[ "$(uname -m)" != "aarch64" ]]' in unix_flash
    assert "direct STM32 flashing is disabled outside the Rock64" in unix_flash
    assert "deployment/scripts/rock64_update_and_flash.sh" in makefile
    assert 'bash "$(REPO_ROOT)/scripts/flash_stm32.sh"' not in makefile
    assert "Development PCs must never flash the STM32 directly" in source_of_truth


def test_rock64_pinout_chart_documents_production_motor_boundary():
    pinout = _read("docs/ROCK64_PI2_BUS_PINOUT.md")
    assert "| 3 | GPIO2_D1 / I2C0_SDA | I2C0 data |" in pinout
    assert "| 5 | GPIO2_D0 / I2C0_SCL | I2C0 clock |" in pinout
    assert "| 8 | GPIO2_A0 / UART2_TX_M1 | UART2 TX |" in pinout
    assert "| 10 | GPIO2_A1 / UART2_RX_M1 | UART2 RX |" in pinout
    assert "| 19 | GPIO3_A1 / SPI_TXD_M2 | SPI MOSI |" in pinout
    assert "/dev/rock64_stm32" in pinout
    assert "not driven from bare Rock64 GPIO pins" in pinout


def test_host_motor_commands_use_full_protocol_range_without_extra_speed_cap():
    bridge = _read("host_ws/src/robot_drivers/robot_drivers/stm32_hardened_bridge.py")
    hardware = _read("host_ws/src/robot_bringup/config/rock64_hardware.yaml")
    directive = _read("docs/TANK_ROBOT_EXECUTION_DIRECTIVE.md")

    assert '"motor_output_limit", 1.0' in bridge
    assert '"stall_current_limit_a", 1.5' in bridge
    assert "self._command_speed_limit" in bridge
    assert "left_vel * self._command_speed_limit" in bridge
    assert "motor_output_limit: 1.0" in hardware
    assert "stall_current_limit_a: 1.5" in hardware
    assert "full signed motor-command range" in directive


def test_runner_is_stable_in_minimal_ssh_ros_environment():
    runner = _read("scripts/e2e_mission.py")

    assert 'PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"' in runner
    assert '"--preset", "Release"' in runner
    assert '"--build", "--preset", "Release"' in runner
    assert 'ros_bin = ros_setup.parent / "bin"' in runner
