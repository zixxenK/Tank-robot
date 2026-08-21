#!/usr/bin/env python3
"""One-shot Tank Robot E2E mission runner with operator-first reporting."""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
HOST_WS = ROOT / "host_ws"
LOG_ROOT = ROOT / "log" / "e2e"
PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"

PYTEST_PATHS = [
    "tests",
    "host_ws/src/agent_core/test",
    "host_ws/src/robot_drivers/test",
    "host_ws/src/robot_teleop/test",
    "host_ws/src/robot_audio/test",
]
PYTEST_IGNORES = [
    "host_ws/src/agent_core/test/test_flake8.py",
    "host_ws/src/agent_core/test/test_pep257.py",
    "host_ws/src/robot_drivers/test/test_flake8.py",
    "host_ws/src/robot_drivers/test/test_pep257.py",
]
ROS_PACKAGES = (
    "agent_core robot_bringup robot_drivers robot_teleop robot_audio "
    "navigation perception telemetry_logger terrain_adaptation"
)


@dataclass
class StageResult:
    """A compact operator-facing result for one mission stage."""

    name: str
    status: str
    required: bool
    components: list[str]
    detail: str
    next_step: str
    duration_s: float
    log_path: str | None = None
    returncode: int | None = None


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _display_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _command_text(command: Sequence[str] | str) -> str:
    if isinstance(command, str):
        return command
    return " ".join(shlex.quote(str(part)) for part in command)


def _write_log_header(
    log_file: Path,
    stage_name: str,
    command: Sequence[str] | str,
    cwd: Path,
) -> None:
    with log_file.open("w", encoding="utf-8", errors="replace") as stream:
        stream.write(f"stage: {stage_name}\n")
        stream.write(f"cwd: {cwd}\n")
        stream.write(f"command: {_command_text(command)}\n")
        stream.write("\n")


def _append_log(log_file: Path, label: str, text: str) -> None:
    with log_file.open("a", encoding="utf-8", errors="replace") as stream:
        stream.write(f"[{label}]\n")
        stream.write(text or "")
        if text and not text.endswith("\n"):
            stream.write("\n")
        stream.write("\n")


def _plain_failure(text: str, returncode: int | None) -> str:
    clean = text.replace("\r\n", "\n").replace("\r", "\n")
    if "ERROR collecting" in clean:
        useful_lines = []
        for line in clean.splitlines():
            stripped = line.strip()
            if (
                "ERROR collecting" in stripped
                or stripped.startswith("E   ")
                or stripped.startswith("ImportError:")
                or stripped.startswith("TypeError:")
            ):
                useful_lines.append(stripped.removeprefix("E   ").strip())
        if useful_lines:
            return " ".join(useful_lines)[:420]
    patterns = [
        r"=+\s*short test summary info\s*=+\n(?P<body>.*?)(?:\n=+|\Z)",
        r"(?P<body>\d+\s+failed.*)",
        r"(?P<body>CMake Error.*)",
        r"(?P<body>ninja: build stopped.*)",
        r"(?P<body>colcon build .*failed.*)",
        r"(?P<body>ERROR:?.*)",
        r"(?P<body>FAILED.*)",
    ]
    for pattern in patterns:
        match = re.search(pattern, clean, flags=re.IGNORECASE | re.DOTALL)
        if match:
            body = match.group("body").strip()
            one_line = " ".join(body.split())
            return one_line[:420]
    if returncode is not None:
        return f"Command exited with code {returncode}; inspect the stage log."
    return "Command did not complete; inspect the stage log."


def _plain_success(text: str, default: str) -> str:
    clean = " ".join(text.replace("\r", "\n").split())
    pytest_match = re.search(r"(\d+)\s+passed(?:,\s*(\d+)\s+skipped)?", clean)
    if pytest_match:
        skipped = pytest_match.group(2)
        if skipped:
            return f"{pytest_match.group(1)} tests passed, {skipped} skipped."
        return f"{pytest_match.group(1)} tests passed."
    cmake_match = re.search(r"Built target\s+([A-Za-z0-9_.-]+)", clean)
    if cmake_match:
        return f"Firmware target built: {cmake_match.group(1)}."
    colcon_match = re.search(r"Summary:\s+(.+)", clean)
    if colcon_match:
        return f"ROS workspace build summary: {colcon_match.group(1)}"
    return default


def _run_process(
    command: Sequence[str] | str,
    cwd: Path,
    log_file: Path,
    timeout_s: int,
    env: Mapping[str, str] | None = None,
    shell: bool = False,
) -> tuple[int, str]:
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        env=dict(env) if env is not None else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_s,
        shell=shell,
        check=False,
    )
    _append_log(log_file, "stdout", completed.stdout)
    _append_log(log_file, "stderr", completed.stderr)
    return completed.returncode, completed.stdout + "\n" + completed.stderr


def run_command_stage(
    *,
    name: str,
    command: Sequence[str] | str,
    components: list[str],
    log_dir: Path,
    required: bool,
    cwd: Path = ROOT,
    timeout_s: int = 300,
    success_detail: str,
    next_step: str,
    env: Mapping[str, str] | None = None,
    shell: bool = False,
) -> StageResult:
    started = time.monotonic()
    log_file = log_dir / (re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").lower() + ".log")
    _write_log_header(log_file, name, command, cwd)
    try:
        returncode, output = _run_process(
            command, cwd, log_file, timeout_s, env=env, shell=shell
        )
    except FileNotFoundError as exc:
        _append_log(log_file, "runner", str(exc))
        return StageResult(
            name=name,
            status=FAIL if required else SKIP,
            required=required,
            components=components,
            detail=f"Required executable was not found: {exc.filename}",
            next_step=next_step,
            duration_s=time.monotonic() - started,
            log_path=_display_path(log_file),
            returncode=127,
        )
    except subprocess.TimeoutExpired as exc:
        _append_log(log_file, "timeout", str(exc))
        return StageResult(
            name=name,
            status=FAIL if required else SKIP,
            required=required,
            components=components,
            detail=f"Stage timed out after {timeout_s} seconds.",
            next_step=next_step,
            duration_s=time.monotonic() - started,
            log_path=_display_path(log_file),
            returncode=124,
        )

    status = PASS if returncode == 0 else FAIL
    detail = (
        _plain_success(output, success_detail)
        if status == PASS
        else _plain_failure(output, returncode)
    )
    return StageResult(
        name=name,
        status=status,
        required=required,
        components=components,
        detail=detail,
        next_step="No action needed." if status == PASS else next_step,
        duration_s=time.monotonic() - started,
        log_path=_display_path(log_file),
        returncode=returncode,
    )


def run_sequence_stage(
    *,
    name: str,
    commands: Sequence[Sequence[str] | str],
    components: list[str],
    log_dir: Path,
    required: bool,
    cwd: Path,
    timeout_s: int,
    success_detail: str,
    next_step: str,
    env: Mapping[str, str] | None = None,
    shell: bool = False,
) -> StageResult:
    started = time.monotonic()
    log_file = log_dir / (re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").lower() + ".log")
    _write_log_header(log_file, name, " && ".join(_command_text(cmd) for cmd in commands), cwd)
    output_parts: list[str] = []
    returncode = 0
    try:
        for command in commands:
            _append_log(log_file, "command", _command_text(command))
            returncode, output = _run_process(
                command, cwd, log_file, timeout_s, env=env, shell=shell
            )
            output_parts.append(output)
            if returncode != 0:
                break
    except FileNotFoundError as exc:
        _append_log(log_file, "runner", str(exc))
        returncode = 127
        output_parts.append(str(exc))
    except subprocess.TimeoutExpired as exc:
        _append_log(log_file, "timeout", str(exc))
        returncode = 124
        output_parts.append(str(exc))

    output = "\n".join(output_parts)
    status = PASS if returncode == 0 else FAIL
    detail = (
        _plain_success(output, success_detail)
        if status == PASS
        else _plain_failure(output, returncode)
    )
    return StageResult(
        name=name,
        status=status,
        required=required,
        components=components,
        detail=detail,
        next_step="No action needed." if status == PASS else next_step,
        duration_s=time.monotonic() - started,
        log_path=_display_path(log_file),
        returncode=returncode,
    )


def skip_stage(
    *,
    name: str,
    components: list[str],
    detail: str,
    next_step: str,
    required: bool = False,
) -> StageResult:
    return StageResult(
        name=name,
        status=SKIP,
        required=required,
        components=components,
        detail=detail,
        next_step=next_step,
        duration_s=0.0,
    )


def tool_missing(*names: str) -> list[str]:
    return [name for name in names if shutil.which(name) is None]


def has_systemd_service(name: str) -> bool:
    if os.name == "nt" or shutil.which("systemctl") is None:
        return False
    completed = subprocess.run(
        ["systemctl", "cat", name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return completed.returncode == 0


def ros_setup_path() -> Path | None:
    if os.name == "nt":
        return None
    distro = os.environ.get("ROS_DISTRO")
    candidates = []
    if distro and distro != "auto":
        candidates.append(Path("/opt/ros") / distro / "setup.bash")
    candidates.append(Path("/opt/ros/humble/setup.bash"))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def environment_stage(log_dir: Path) -> StageResult:
    started = time.monotonic()
    log_file = log_dir / "environment_setup.log"
    _write_log_header(log_file, "Environment setup", [sys.executable, "--version"], ROOT)
    version_text = sys.version.replace("\n", " ")
    _append_log(log_file, "runner", f"Python executable: {sys.executable}\nPython version: {version_text}\n")
    if sys.version_info < (3, 10):
        return StageResult(
            name="Environment setup",
            status=FAIL,
            required=True,
            components=["Mission Runner", "Environment"],
            detail=(
                "Python 3.10 or newer is required by the ROS package code; "
                f"this command used Python {sys.version_info.major}.{sys.version_info.minor}."
            ),
            next_step=(
                "Install Python 3.10+ in this shell, or run .\\run_e2e.ps1 "
                "from Windows PowerShell where Python 3.12 is available."
            ),
            duration_s=time.monotonic() - started,
            log_path=_display_path(log_file),
            returncode=1,
        )
    return StageResult(
        name="Environment setup",
        status=PASS,
        required=True,
        components=["Mission Runner", "Environment"],
        detail="Mission workspace, log capture, and Python runtime are ready.",
        next_step="No action needed.",
        duration_s=time.monotonic() - started,
        log_path=_display_path(log_file),
        returncode=0,
    )


def pytest_stage(log_dir: Path) -> StageResult:
    command = [sys.executable, "-m", "pytest", *PYTEST_PATHS]
    for ignored in PYTEST_IGNORES:
        command.append(f"--ignore={ignored}")
    command.append("-q")
    env = os.environ.copy()
    # A system-installed pytest on Ubuntu can discover a newer user-local
    # plugin (for example anyio) that is incompatible with the distro pytest.
    # The mission suite is intentionally self-contained, so third-party plugin
    # autoloading must not make the one-shot result environment-dependent.
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    python_paths = [
        str(ROOT / "stubs"),
        str(HOST_WS / "src" / "agent_core"),
        str(HOST_WS / "src" / "robot_drivers"),
        str(HOST_WS / "src" / "robot_teleop"),
        str(HOST_WS / "src" / "robot_audio"),
        str(HOST_WS / "src" / "navigation"),
        str(HOST_WS / "src" / "perception"),
        str(HOST_WS / "src" / "telemetry_logger"),
        str(HOST_WS / "src" / "terrain_adaptation"),
    ]
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = os.pathsep.join(
        python_paths + ([existing] if existing else [])
    )
    return run_command_stage(
        name="Offline full-stack contract tests",
        command=command,
        components=[
            "Safety Gateway",
            "STM32 Comms Parser",
            "Motor Driver Contracts",
            "Chassis Control",
            "Navigation",
            "Teleop",
            "Launch Files",
            "ROS Stubs",
        ],
        log_dir=log_dir,
        required=True,
        timeout_s=300,
        success_detail="Offline host logic and simulated ROS contracts passed.",
        next_step=(
            "Open the stage log, fix the named failing test or import, then "
            "rerun the one-shot command."
        ),
        env=env,
    )


def firmware_stage(log_dir: Path) -> StageResult:
    missing = tool_missing("cmake", "ninja", "arm-none-eabi-gcc")
    if missing:
        return skip_stage(
            name="STM32 firmware build",
            components=["STM32 Firmware", "Motor Controller"],
            detail=f"Toolchain not available on this machine: {', '.join(missing)}.",
            next_step=(
                "Install CMake, Ninja, and ARM GNU Toolchain, or run this on "
                "the Rock64 build host."
            ),
        )
    firmware_dir = ROOT / "firmware" / "stm32_chassis"
    return run_sequence_stage(
        name="STM32 firmware build",
        commands=[
            # Do not force a generator here. This reuses an existing build
            # directory (Makefiles on the Rock64 release path, Ninja on some
            # developer machines) and avoids generator-cache collisions.
            [
                "cmake",
                "-S",
                ".",
                "-B",
                "build/Release",
                "-DCMAKE_BUILD_TYPE=Release",
                "-DCMAKE_TOOLCHAIN_FILE=cmake/gcc-arm-none-eabi.cmake",
            ],
            ["cmake", "--build", "build/Release", "--parallel", "4"],
        ],
        components=["STM32 Firmware", "Motor Controller", "Watchdog"],
        log_dir=log_dir,
        required=True,
        cwd=firmware_dir,
        timeout_s=600,
        success_detail="STM32 Release firmware built successfully.",
        next_step=(
            "Check the firmware build log for the first compiler or linker "
            "error, then rerun this command after the source or toolchain fix."
        ),
    )


def ros_build_stage(log_dir: Path) -> StageResult:
    missing = tool_missing("bash", "colcon")
    setup = ros_setup_path()
    if setup is None:
        missing.append("ROS 2 setup.bash")
    if missing:
        return skip_stage(
            name="ROS workspace build",
            components=["ROS 2 Workspace", "Launch Graph"],
            detail=f"ROS build environment not available: {', '.join(missing)}.",
            next_step=(
                "Run the one-shot command on Ubuntu 22.04 with ROS 2 Humble "
                "and colcon installed to exercise the native ROS build."
            ),
        )
    command = (
        # ROS Humble's setup scripts reference optional variables while they
        # are being initialized. Do not enable nounset until after sourcing.
        "set -eo pipefail; "
        f"source {shlex.quote(str(setup))}; "
        "set -u; "
        f"cd {shlex.quote(str(HOST_WS))}; "
        f"colcon build --symlink-install --packages-up-to {ROS_PACKAGES}"
    )
    return run_command_stage(
        name="ROS workspace build",
        command=["bash", "-lc", command],
        components=["ROS 2 Workspace", "Launch Graph", "Runtime Packaging"],
        log_dir=log_dir,
        required=True,
        cwd=ROOT,
        timeout_s=900,
        success_detail="ROS workspace packages built successfully.",
        next_step=(
            "Inspect the ROS build log for the package named by colcon, fix "
            "that package, then rerun the one-shot command."
        ),
    )


def hardware_results_from_log(log_path: str | None) -> list[tuple[str, str, str]]:
    """Extract compact acceptance results from the captured runner log."""
    if not log_path:
        return []
    path = Path(log_path)
    if not path.is_absolute():
        path = ROOT / path
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    pattern = re.compile(
        r"\[(?:INFO|ERROR|WARN)\].*?\[hardware_test_runner\]: "
        r"\[\d+\] (?P<status>PASS|FAIL|SKIP): "
        r"(?P<name>[^-\r\n]+?) - (?P<detail>[^\r\n]+)"
    )
    return [
        (
            match.group("status"),
            match.group("name").strip(),
            " ".join(match.group("detail").split()),
        )
        for match in pattern.finditer(text)
    ]


def hardware_result_line(
    hardware: StageResult | None,
    target: str,
    fallback: str,
) -> str:
    """Return one clean subsystem line without exposing captured log noise."""
    if hardware is None:
        return fallback
    for status, name, detail in hardware_results_from_log(hardware.log_path):
        if name == target:
            return f"{status} - {detail}"
    return fallback


def hardware_acceptance_stage(log_dir: Path) -> StageResult:
    missing = tool_missing("bash", "ros2")
    if missing:
        return skip_stage(
            name="Live Rock64 hardware acceptance",
            components=["STM32 Link", "Motor Drivers", "E-Stop", "Sensors"],
            detail=f"Live ROS hardware runtime not available: {', '.join(missing)}.",
            next_step=(
                "Run the same one-shot command on the Rock64 after deployment "
                "to validate the physical STM32, sensors, cameras, and e-stop."
            ),
        )
    if not has_systemd_service("rock64-robot.service"):
        return skip_stage(
            name="Live Rock64 hardware acceptance",
            components=["STM32 Link", "Motor Drivers", "E-Stop", "Sensors"],
            detail="rock64-robot.service is not installed on this machine.",
            next_step=(
                "Deploy to the Rock64 or install the service, then rerun the "
                "one-shot command there. The default run remains non-motion."
            ),
        )
    result = run_command_stage(
        name="Live Rock64 hardware acceptance",
        command=["bash", str(ROOT / "scripts" / "hardware_acceptance.sh"), "--no-lidar"],
        components=[
            "STM32 Link",
            "Encoder Stream",
            "IMU",
            "HC-SR04",
            "PS5 Input",
            "Camera Bridges",
            "Servo Command Path",
            "E-Stop",
        ],
        log_dir=log_dir,
        required=True,
        timeout_s=420,
        success_detail="Live non-motion hardware acceptance passed.",
        next_step=(
            "Use the named failing hardware stage in the log to check wiring, "
            "udev device paths, service health, or sensor power."
        ),
    )
    details = hardware_results_from_log(result.log_path)
    failures = [f"{name}: {detail}" for status, name, detail in details if status == FAIL]
    if failures:
        result.detail = "Live acceptance failures: " + "; ".join(failures)[:700]
    elif details:
        passed = sum(status == PASS for status, _, _ in details)
        skipped = sum(status == SKIP for status, _, _ in details)
        result.detail = (
            f"Live acceptance passed: {passed} checks"
            + (f", {skipped} optional checks skipped" if skipped else "")
            + "."
        )
    return result


def teardown_stage(log_dir: Path, hardware_ran: bool) -> StageResult:
    if not hardware_ran:
        return StageResult(
            name="Teardown and cleanup",
            status=PASS,
            required=True,
            components=["Runtime Cleanup"],
            detail="No live hardware test process was started on this machine.",
            next_step="No action needed.",
            duration_s=0.0,
        )
    if tool_missing("bash"):
        return skip_stage(
            name="Teardown and cleanup",
            components=["Runtime Cleanup"],
            detail="Bash is unavailable, so cleanup_runtime.sh could not run.",
            next_step="Stop stale ROS launch/run processes manually if needed.",
            required=True,
        )
    return run_command_stage(
        name="Teardown and cleanup",
        command=["bash", str(ROOT / "scripts" / "cleanup_runtime.sh")],
        components=["Runtime Cleanup", "ROS Daemon"],
        log_dir=log_dir,
        required=True,
        timeout_s=60,
        success_detail="Runtime cleanup completed.",
        next_step=(
            "Check for stale ros2 launch or ros2 run processes and stop only "
            "operator-owned test processes."
        ),
    )


def mission_document(results: list[StageResult], log_dir: Path) -> dict:
    required_failures = [
        result for result in results if result.required and result.status == FAIL
    ]
    return {
        "schema_version": 1,
        "started_at": log_dir.name,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "overall_status": FAIL if required_failures else PASS,
        "log_dir": _display_path(log_dir),
        "results": [asdict(result) for result in results],
    }


def print_report(results: list[StageResult], log_dir: Path, report_path: Path) -> None:
    document = mission_document(results, log_dir)
    anomalies = [result for result in results if result.status != PASS]
    deployment_time = sum(result.duration_s for result in results)

    def stage(name: str) -> StageResult | None:
        for result in results:
            if result.name == name:
                return result
        return None

    def status_line(result: StageResult | None, fallback: str) -> str:
        if result is None:
            return fallback
        if result.status == PASS:
            return f"PASS - {result.detail}"
        if result.status == SKIP:
            return f"SKIP - {result.detail}"
        return f"FAIL - {result.detail}"

    hardware = stage("Live Rock64 hardware acceptance")
    offline = stage("Offline full-stack contract tests")
    encoder_line = hardware_result_line(
        hardware,
        "STM32 encoder stream",
        "SKIP - live hardware was not exercised; ticks unavailable",
    )
    left_encoder = encoder_line
    right_encoder = encoder_line

    print("\n=== TANK-ROBOT SYSTEM REPORT ===")
    print(f"[ OVERALL STATUS ]: {document['overall_status']}")
    print(f"[ DEPLOYMENT TIME ]: {deployment_time:.2f}s")
    print("")
    print("[ SUBSYSTEMS ]:")
    print(
        "- Rock64 to STM32 Comms: "
        + hardware_result_line(
            hardware,
            "STM32 bridge alive",
            "SKIP - live Rock64 hardware was not present",
        )
    )
    print(f"- Motor 1 (Left Track) Encoders: {left_encoder}")
    print(f"- Motor 2 (Right Track) Encoders: {right_encoder}")
    print(f"- Kinematics/PID Nodes: {status_line(offline, 'SKIP - offline contracts were not run')}")
    print("")
    print("[ ANOMALIES ]:")
    if anomalies:
        for result in anomalies:
            severity = "Required failure" if result.required and result.status == FAIL else "Not exercised"
            print(f"- {severity}: {result.name}. {result.detail}")
    else:
        print("None")

    print("")
    print("[ NEXT STEPS ]:")
    if anomalies:
        for result in anomalies:
            print(f"- {result.name}: {result.next_step}")
    else:
        print("- Teleop: bash scripts/onecmd.sh")
        print("- Autonomous: ros2 launch robot_bringup full_stack.launch.py")
    print("================================")


def main() -> int:
    log_dir = LOG_ROOT / _timestamp()
    log_dir.mkdir(parents=True, exist_ok=True)
    results: list[StageResult] = []

    environment_result = environment_stage(log_dir)
    results.append(environment_result)
    if environment_result.status == PASS:
        # SSH-launched services often have a minimal PATH and do not source
        # /opt/ros/humble/setup.bash. Add the ROS CLI directory for discovery;
        # stages that need the full overlay still source setup.bash explicitly.
        ros_setup = ros_setup_path()
        if ros_setup is not None:
            ros_bin = ros_setup.parent / "bin"
            current_path = os.environ.get("PATH", "")
            if ros_bin.is_dir() and str(ros_bin) not in current_path.split(os.pathsep):
                os.environ["PATH"] = os.pathsep.join(
                    [str(ros_bin), current_path] if current_path else [str(ros_bin)]
                )
        results.append(pytest_stage(log_dir))
        results.append(firmware_stage(log_dir))
        results.append(ros_build_stage(log_dir))
        hardware_result = hardware_acceptance_stage(log_dir)
        results.append(hardware_result)
        results.append(teardown_stage(log_dir, hardware_result.log_path is not None))
    else:
        results.extend(
            [
                skip_stage(
                    name="Offline full-stack contract tests",
                    components=[
                        "Safety Gateway",
                        "STM32 Comms Parser",
                        "Motor Driver Contracts",
                        "Chassis Control",
                    ],
                    detail="Blocked by the failed environment gate.",
                    next_step=environment_result.next_step,
                ),
                skip_stage(
                    name="STM32 firmware build",
                    components=["STM32 Firmware", "Motor Controller"],
                    detail="Blocked by the failed environment gate.",
                    next_step=environment_result.next_step,
                ),
                skip_stage(
                    name="ROS workspace build",
                    components=["ROS 2 Workspace", "Launch Graph"],
                    detail="Blocked by the failed environment gate.",
                    next_step=environment_result.next_step,
                ),
                skip_stage(
                    name="Live Rock64 hardware acceptance",
                    components=["STM32 Link", "Motor Drivers", "E-Stop", "Sensors"],
                    detail="Blocked by the failed environment gate.",
                    next_step=environment_result.next_step,
                ),
                teardown_stage(log_dir, False),
            ]
        )

    report_path = log_dir / "mission_report.json"
    report_path.write_text(
        json.dumps(mission_document(results, log_dir), indent=2) + "\n",
        encoding="utf-8",
    )
    print_report(results, log_dir, report_path)

    return 1 if any(
        result.required and result.status == FAIL for result in results
    ) else 0


if __name__ == "__main__":
    raise SystemExit(main())
