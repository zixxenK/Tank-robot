#!/usr/bin/env python3
"""Local Tank-Robot operator service.

This service is intentionally localhost-only.  It owns the small amount of
orchestration that cannot be expressed by ROS launch files: starting/stopping
the simulation container, synchronizing the Rock64 over SSH, and maintaining
the optional Foxglove tunnel.  Secrets are accepted only for the duration of
one operation and are never written to the operator volume or logs.
"""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import tempfile
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from shlex import quote
from typing import Any


ROOT = Path(os.environ.get("TANKROBOT_SOURCE_ROOT", "/opt/tankrobot"))
DATA = Path(os.environ.get("TANKROBOT_DATA", "/var/lib/tankrobot"))
CONFIG_PATH = DATA / "config.json"
KEY_PATH = DATA / "id_ed25519"
PUBLIC_KEY_PATH = DATA / "id_ed25519.pub"
PORT = int(os.environ.get("TANKROBOT_OPERATOR_PORT", "8787"))
SIM_SERVICE = os.environ.get("TANKROBOT_SIM_SERVICE", "tankrobot-sim-1")
DIRECT_FOXGLOVE_PORT = os.environ.get("TANKROBOT_DIRECT_FOXGLOVE_PORT", "8767")
SIM_FOXGLOVE_PORT = os.environ.get("TANKROBOT_SIM_FOXGLOVE_PORT", "28766")
SSH_FOXGLOVE_PORT = os.environ.get("TANKROBOT_SSH_FOXGLOVE_PORT", "28765")

LOCK = threading.RLock()
JOB: dict[str, Any] = {"state": "idle", "name": "", "message": ""}
LOGS: deque[str] = deque(maxlen=250)
TUNNEL: subprocess.Popen[bytes] | None = None
DIRECT_DASHBOARD: subprocess.Popen[bytes] | None = None
DISCOVERED_HOSTS: list[str] = []


def log(message: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {message}"
    with LOCK:
        LOGS.append(line)
    print(line, flush=True)


def load_config() -> dict[str, str]:
    defaults = {
        "robot_host": "auto",
        "robot_user": "rock64",
        "remote_root": "/opt/rock64-robot",
        "connection_mode": "ssh",
        "discovery_server": "",
        "flash_esp32": "true",
    }
    try:
        values = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if isinstance(values, dict):
            defaults.update({k: str(v) for k, v in values.items() if k in defaults})
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return defaults


def save_config(values: dict[str, str]) -> dict[str, str]:
    DATA.mkdir(parents=True, exist_ok=True)
    current = load_config()
    for key in current:
        if key in values:
            current[key] = str(values[key])
    CONFIG_PATH.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    return current


def ensure_key() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    if KEY_PATH.exists() and PUBLIC_KEY_PATH.exists():
        return
    result = subprocess.run(
        ["ssh-keygen", "-t", "ed25519", "-N", "", "-f", str(KEY_PATH)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "ssh-keygen failed")
    os.chmod(KEY_PATH, 0o600)


def public_key() -> str:
    ensure_key()
    return PUBLIC_KEY_PATH.read_text(encoding="utf-8").strip()


def run(
    command: list[str],
    *,
    input_text: str | None = None,
    timeout: int = 30,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        input=input_text,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
        check=False,
    )


def validate_connection(config: dict[str, str]) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_.:-]+", config["robot_host"]):
        raise RuntimeError("Robot hostname/IP contains unsupported characters.")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", config["robot_user"]):
        raise RuntimeError("Rock64 SSH username contains unsupported characters.")


def password_ssh(
    command: str,
    config: dict[str, str],
    password: str,
    *,
    input_text: str | None = None,
    timeout: int = 30,
) -> str:
    """Run one password-authenticated SSH command without putting the password in argv."""
    validate_connection(config)
    if not shutil.which("sshpass"):
        raise RuntimeError("The operator image is missing sshpass; rebuild the Docker image.")
    environment = os.environ.copy()
    environment["SSHPASS"] = password
    result = run(
        [
            "sshpass", "-e", "ssh",
            "-o", "PreferredAuthentications=password",
            "-o", "PubkeyAuthentication=no",
            "-o", "NumberOfPasswordPrompts=1",
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "ConnectTimeout=6",
            f"{config['robot_user']}@{config['robot_host']}",
            command,
        ],
        input_text=input_text,
        timeout=timeout,
        env=environment,
    )
    if result.returncode:
        detail = (result.stderr or "").lower()
        if "permission denied" in detail or "authentication" in detail:
            raise RuntimeError(
                "Rock64 login failed: check the username/password, or enable SSH password authentication for setup."
            )
        if any(text in detail for text in ("could not resolve", "connection timed out", "no route", "refused")):
            raise RuntimeError("Rock64 is unreachable at the discovered address.")
        raise RuntimeError("Initial Rock64 SSH setup failed.")
    return (result.stdout or "").strip()


def _ssh_port_open(host: str) -> bool:
    try:
        with socket.create_connection((host, 22), timeout=0.35):
            return True
    except (OSError, ValueError):
        return False


def discover_hosts() -> list[str]:
    """Find SSH endpoints commonly used by Windows, Android, and iOS hotspots."""
    candidates: list[str] = ["rock64.local", "rock64"]
    # Windows Mobile Hotspot defaults to 192.168.137.0/24. The other ranges
    # cover common phone hotspots; scanning is bounded and only tests TCP/22.
    for prefix in ("192.168.137", "192.168.43", "172.20.10", "192.168.42", "192.168.1"):
        candidates.extend(f"{prefix}.{number}" for number in range(2, 255))
    resolved: list[str] = []
    for candidate in candidates[:2]:
        try:
            resolved.extend(item[4][0] for item in socket.getaddrinfo(candidate, 22, type=socket.SOCK_STREAM))
        except (OSError, ValueError):
            pass
    candidates = list(dict.fromkeys(resolved + candidates[2:]))
    found: list[str] = []
    with ThreadPoolExecutor(max_workers=64) as executor:
        checks = {executor.submit(_ssh_port_open, candidate): candidate for candidate in candidates}
        for future in as_completed(checks):
            if future.result():
                found.append(checks[future])
    # Prefer the stable mDNS name when it is available, and keep UI ordering
    # deterministic for a multi-device hotspot.
    return sorted(set(found), key=lambda value: (0 if value in {"rock64.local", "rock64"} else 1, value))


def install_ssh_key(config: dict[str, str], password: str) -> None:
    key = public_key()
    install = (
        "set -eu; umask 077; mkdir -p \"$HOME/.ssh\"; "
        "touch \"$HOME/.ssh/authorized_keys\"; "
        f"grep -Fqx -- {quote(key)} \"$HOME/.ssh/authorized_keys\" || "
        f"printf '%s\\n' {quote(key)} >> \"$HOME/.ssh/authorized_keys\"; "
        "chmod 700 \"$HOME/.ssh\"; chmod 600 \"$HOME/.ssh/authorized_keys\""
    )
    password_ssh(install, config, password, timeout=30)
    result = run(ssh_base(config) + ["true"], timeout=12)
    if result.returncode:
        raise RuntimeError("The key was installed, but passwordless SSH verification failed.")


def setup_ssh(payload: dict[str, Any]) -> dict[str, str]:
    """Provision key auth using a one-time password, then forget that password."""
    password = str(payload.get("ssh_password", ""))
    if not password:
        raise RuntimeError("Enter the Rock64 login password for the one-time automatic SSH setup.")
    config = save_config({
        k: str(payload[k]) for k in ("robot_host", "robot_user", "remote_root", "connection_mode", "discovery_server")
        if k in payload
    })
    requested = config["robot_host"].strip()
    try:
        validate_connection({**config, "robot_host": requested or "auto"}) if requested not in {"", "auto"} else None
        hosts = [requested] if requested not in {"", "auto"} else discover_hosts()
        if not hosts:
            raise RuntimeError("No Rock64 SSH host was found. Connect the robot to this PC hotspot and try again.")
        if requested in {"", "auto"} and len(hosts) > 1:
            raise RuntimeError("Multiple SSH devices were found: " + ", ".join(hosts) + ". Select the Rock64 host and retry.")
        config = save_config({"robot_host": hosts[0]})
        install_ssh_key(config, password)
        log(f"Automatic SSH setup verified for {config['robot_user']}@{config['robot_host']}.")
        return config
    finally:
        # Rebind the local reference immediately; the password is never put in
        # config, logs, command arguments, or the operator job state.
        password = ""


def ssh_base(config: dict[str, str]) -> list[str]:
    ensure_key()
    return [
        "ssh",
        "-i",
        str(KEY_PATH),
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        "ConnectTimeout=6",
        f"{config['robot_user']}@{config['robot_host']}",
    ]


def remote(command: str, config: dict[str, str], *, password: str = "", timeout: int = 900) -> str:
    ssh = ssh_base(config) + [command]
    result = run(ssh, input_text=(password + "\n") if password else None, timeout=timeout)
    output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
    if output:
        for line in output.splitlines()[-80:]:
            log(line)
    if result.returncode:
        raise RuntimeError(output or f"SSH command failed with exit code {result.returncode}")
    return output


def sudo_remote(command: str, config: dict[str, str], password: str = "", timeout: int = 900) -> str:
    if password:
        wrapped = f"sudo -S -p '' bash -lc {quote(command)}"
    else:
        wrapped = f"sudo -n bash -lc {quote(command)}"
    return remote(wrapped, config, password=password, timeout=timeout)


def docker_state() -> str:
    if not shutil.which("docker"):
        return "Docker CLI unavailable"
    result = run(["docker", "inspect", "--format", "{{.State.Status}}", SIM_SERVICE])
    if result.returncode:
        result = run([
            "docker", "ps", "-a", "--filter", "label=com.docker.compose.service=sim",
            "--format", "{{.State}}",
        ])
    return (result.stdout or "not-created").strip() or "not-created"


def stop_process(process: subprocess.Popen[bytes] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


def stop_simulation() -> None:
    if not shutil.which("docker"):
        return
    result = run(["docker", "stop", SIM_SERVICE], timeout=30)
    if result.returncode == 0:
        log("Simulation container stopped.")


def start_simulation() -> None:
    if not shutil.which("docker"):
        raise RuntimeError("Docker CLI is unavailable inside the operator container.")
    result = run(["docker", "start", SIM_SERVICE], timeout=30)
    if result.returncode:
        raise RuntimeError("Simulation container has not been created; rerun the bootstrap command.")
    log("Simulation container started.")


def make_archive() -> str:
    archive = tempfile.NamedTemporaryFile(prefix="tankrobot-", suffix=".tgz", delete=False)
    archive.close()
    command = [
        "tar", "-czf", archive.name, "-C", str(ROOT),
        "--exclude=.git", "--exclude=.idea", "--exclude=.vscode",
        "--exclude=host_ws/build", "--exclude=host_ws/install", "--exclude=host_ws/log",
        "--exclude=firmware/stm32_chassis/build", "--exclude=firmware/esp32_sensors/.pio",
        "--exclude=log", "--exclude=*.bin", "--exclude=*.elf", "--exclude=*.hex", "--exclude=*.map",
        "deployment", "scripts", "tests", "stubs", "host_ws/src", "firmware/stm32_chassis",
        "firmware/esp32_sensors", "Makefile", "pytest.ini", "run_e2e.sh", "run_e2e.ps1",
    ]
    result = run(command, timeout=120)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Unable to create Rock64 source archive")
    return archive.name


def sync_and_build(config: dict[str, str], password: str) -> None:
    archive = make_archive()
    # Stage in /tmp so a first-time Rock64 user does not need write access to
    # /opt yet; extraction and directory ownership are handled through sudo.
    remote_archive = "/tmp/.tankrobot-sync.tgz"
    target = f"{config['robot_user']}@{config['robot_host']}:{remote_archive}"
    try:
        result = run(["scp", "-i", str(KEY_PATH), "-o", "StrictHostKeyChecking=accept-new", archive, target], timeout=180)
        if result.returncode:
            raise RuntimeError((result.stderr or "scp failed").strip())
        root = quote(config["remote_root"])
        extract = (
            f"set -e; mkdir -p {root}; "
            f"if [ -f {root}/deployment/systemd/systemd_config.conf ]; then cp {root}/deployment/systemd/systemd_config.conf {root}/.tankrobot-systemd.conf; fi; "
            f"rm -rf {root}/deployment {root}/scripts {root}/tests {root}/stubs {root}/host_ws/src {root}/firmware/stm32_chassis {root}/firmware/esp32_sensors; "
            f"tar --no-same-owner -xzf {quote(remote_archive)} -C {root}; "
            f"if [ -f {root}/.tankrobot-systemd.conf ]; then mkdir -p {root}/deployment/systemd; cp {root}/.tankrobot-systemd.conf {root}/deployment/systemd/systemd_config.conf; fi; "
            f"rm -f {root}/.tankrobot-systemd.conf {quote(remote_archive)}; "
            f"find {root}/scripts {root}/deployment/scripts -type f -name '*.sh' -exec chmod 0755 {{}} +; "
            f"chown -R {quote(config['robot_user'])}: {root}"
        )
        sudo_remote(extract, config, password=password, timeout=180)
        # A newly imaged Rock64 may have SSH but no ROS installation or
        # project configuration yet. Bootstrap those prerequisites remotely
        # with the same one-time sudo credential used by the first start.
        ready_check = (
            "if [ ! -f /opt/ros/humble/setup.bash ] || "
            f"[ ! -f {root}/deployment/systemd/systemd_config.conf ]; then "
            f"bash {root}/deployment/scripts/rock64_setup.sh --ros-distro humble "
            f"--rock64-ip {quote(config['robot_host'])}; "
            f"chown -R {quote(config['robot_user'])}: {root}; fi"
        )
        sudo_remote(ready_check, config, password=password, timeout=1800)
        build = (
            f"set -e; export HOST_WS_PATH={quote(config['remote_root'] + '/host_ws')}; "
            f"source {quote(config['remote_root'] + '/deployment/scripts/source_host_ws.sh')}; "
            f"cd \"$HOST_WS_PATH\"; rosdep install --from-paths src --ignore-src -r -y; "
            f"rm -rf {root}/host_ws/build {root}/host_ws/install {root}/host_ws/log; "
            "colcon build --symlink-install"
        )
        remote(build, config, timeout=1800)
        sudo_remote(f"bash {root}/deployment/scripts/apply_systemd.sh", config, password=password, timeout=300)
        log("Rock64 source synchronized, rebuilt, and service started.")
    finally:
        try:
            os.unlink(archive)
        except OSError:
            pass


def start_remote_dashboard(config: dict[str, str], password: str) -> None:
    root = quote(config["remote_root"])
    launch = (
        f"cd {root}; "
        f"if [ -f .tankrobot-dashboard.pid ]; then kill \"$(cat .tankrobot-dashboard.pid)\" 2>/dev/null || true; fi; "
        f"nohup bash -lc {quote('source ' + config['remote_root'] + '/deployment/scripts/source_host_ws.sh; exec ros2 launch robot_bringup pc_dashboard.launch.py use_nav2:=false')} "
        f">.tankrobot-dashboard.log 2>&1 < /dev/null & echo $! > .tankrobot-dashboard.pid"
    )
    remote(launch, config, timeout=30)


def start_tunnel(config: dict[str, str]) -> None:
    global TUNNEL
    stop_process(TUNNEL)
    TUNNEL = subprocess.Popen(
        ssh_base(config)[:1] + [
            "-i", str(KEY_PATH), "-o", "ExitOnForwardFailure=yes",
            "-o", "ServerAliveInterval=15", "-N", "-L", "18765:127.0.0.1:8765",
            f"{config['robot_user']}@{config['robot_host']}",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    time.sleep(1)
    if TUNNEL.poll() is not None:
        error = TUNNEL.stderr.read().decode(errors="replace") if TUNNEL.stderr else "tunnel failed"
        raise RuntimeError(error.strip() or "SSH Foxglove tunnel failed")
    log("SSH Foxglove tunnel listening on ws://127.0.0.1:18765.")


def start_direct_dashboard(config: dict[str, str]) -> None:
    global DIRECT_DASHBOARD
    stop_process(DIRECT_DASHBOARD)
    env = os.environ.copy()
    env["ROS_LOCALHOST_ONLY"] = "0"
    if config.get("discovery_server"):
        env["ROS_DISCOVERY_SERVER"] = config["discovery_server"]
    command = [
        "bash", "-lc",
        "source /opt/ros/humble/setup.bash && source /opt/tankrobot/host_ws/install/setup.bash && "
        "exec ros2 launch robot_bringup pc_dashboard.launch.py foxglove_address:=0.0.0.0",
    ]
    DIRECT_DASHBOARD = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log("Direct DDS dashboard started on ws://127.0.0.1:8765.")


def start_robot(payload: dict[str, Any]) -> None:
    config = save_config({k: str(payload[k]) for k in ("robot_host", "robot_user", "remote_root", "connection_mode", "discovery_server") if k in payload})
    password = str(payload.get("sudo_password", ""))
    if config["robot_host"] in {"", "auto"}:
        raise RuntimeError("Set up SSH automatically first so the Rock64 address can be discovered.")
    validate_connection(config)
    stop_simulation()
    remote("true", config, timeout=15)
    sync_and_build(config, password)
    if config["connection_mode"] == "direct":
        start_direct_dashboard(config)
    else:
        start_remote_dashboard(config, password)
        start_tunnel(config)


def setup_ssh_and_start(payload: dict[str, Any]) -> None:
    """Perform first-time key setup and the initial full robot start in one action."""
    ssh_password = str(payload.get("ssh_password", ""))
    if not ssh_password:
        raise RuntimeError("Enter the Rock64 login password for the one-time automatic SSH setup.")
    try:
        config = setup_ssh(payload)
        start_payload = {k: v for k, v in payload.items() if k != "ssh_password"}
        # Standard Rock64 accounts use the login password for sudo. A separate
        # value remains available for installations that deliberately differ.
        start_payload["sudo_password"] = str(payload.get("sudo_password", "")) or ssh_password
        start_payload.update(config)
        start_robot(start_payload)
    finally:
        ssh_password = ""


def discover_robot(payload: dict[str, Any]) -> None:
    global DISCOVERED_HOSTS
    found = discover_hosts()
    with LOCK:
        DISCOVERED_HOSTS = found
    if found:
        log("SSH devices found: " + ", ".join(found))
        if len(found) == 1 and str(payload.get("robot_host", "auto")) in {"", "auto"}:
            save_config({"robot_host": found[0]})
    else:
        log("No SSH device found. Ensure the Rock64 is connected to this PC hotspot.")


def stop_robot(payload: dict[str, Any]) -> None:
    config = load_config()
    global TUNNEL, DIRECT_DASHBOARD
    stop_process(TUNNEL)
    stop_process(DIRECT_DASHBOARD)
    TUNNEL = None
    DIRECT_DASHBOARD = None
    root = quote(config["remote_root"])
    remote(f"cd {root} && if [ -f .tankrobot-dashboard.pid ]; then kill \"$(cat .tankrobot-dashboard.pid)\" 2>/dev/null || true; rm -f .tankrobot-dashboard.pid; fi", config, timeout=30)
    sudo_remote("systemctl stop rock64-robot.service", config, password=str(payload.get("sudo_password", "")), timeout=60)
    log("Rock64 service and dashboard stopped.")


def flash_robot(payload: dict[str, Any]) -> None:
    if str(payload.get("confirmation", "")) != "FLASH":
        raise RuntimeError("Firmware flashing requires the exact confirmation word FLASH.")
    config = load_config()
    password = str(payload.get("sudo_password", ""))
    sync_and_build(config, password)
    flash_esp32 = "true" if str(payload.get("flash_esp32", config["flash_esp32"])).lower() in {"1", "true", "yes"} else "false"
    root = quote(config["remote_root"])
    sudo_remote(
        f"cd {root} && FLASH_ESP32={quote(flash_esp32)} bash deployment/scripts/rock64_update_and_flash.sh",
        config,
        password=password,
        timeout=2400,
    )
    log("Firmware flash and verification completed on the Rock64.")


def launch_job(name: str, function, payload: dict[str, Any]) -> None:
    global JOB
    with LOCK:
        if JOB["state"] == "running":
            raise RuntimeError("Another operator action is already running.")
        JOB = {"state": "running", "name": name, "message": ""}

    def worker() -> None:
        global JOB
        try:
            log(f"Starting action: {name}")
            function(payload)
            with LOCK:
                JOB = {"state": "complete", "name": name, "message": "Completed successfully."}
        except Exception as exc:  # noqa: BLE001 - surface operator failures in UI
            log(f"Action failed: {exc}")
            with LOCK:
                JOB = {"state": "failed", "name": name, "message": str(exc)}

    threading.Thread(target=worker, daemon=True).start()


def status() -> dict[str, Any]:
    config = load_config()
    robot = "not-configured" if config["robot_host"] in {"", "auto"} else "not-checked"
    if robot != "not-configured":
        try:
            result = run(ssh_base(config) + ["true"], timeout=10)
            robot = "reachable" if result.returncode == 0 else "unreachable"
        except (OSError, subprocess.TimeoutExpired):
            robot = "unreachable"
    with LOCK:
        job = dict(JOB)
        logs = list(LOGS)[-40:]
        discovered = list(DISCOVERED_HOSTS)
    mode = config["connection_mode"]
    foxglove = f"ws://127.0.0.1:{SSH_FOXGLOVE_PORT}" if mode == "ssh" else f"ws://127.0.0.1:{DIRECT_FOXGLOVE_PORT}"
    return {
        "simulation": docker_state(),
        "robot": robot,
        "config": config,
        "discovered_hosts": discovered,
        "public_key": public_key(),
        "job": job,
        "foxglove_url": foxglove,
        "simulation_foxglove_url": f"ws://127.0.0.1:{SIM_FOXGLOVE_PORT}",
        "logs": logs,
    }


HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tank Robot Operator</title>
<style>
body{font:16px system-ui,sans-serif;max-width:980px;margin:2rem auto;padding:0 1rem;background:#101318;color:#e8edf2}
button,input,select{font:inherit;padding:.55rem;margin:.25rem 0;background:#202832;color:inherit;border:1px solid #536273;border-radius:5px}
button{cursor:pointer}button:hover{background:#304052}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:1rem}
section{background:#171d24;padding:1rem;border-radius:8px;border:1px solid #2b3541}pre{white-space:pre-wrap;max-height:260px;overflow:auto;color:#b8c7d9}
.good{color:#67d391}.warn{color:#f4c36a}.bad{color:#ff7d7d}.danger{border-color:#b24b4b}
small{color:#9aa8b7}.wide{grid-column:1/-1}label{display:block;margin-top:.5rem}
</style></head><body>
<h1>Tank Robot Operator</h1><p><small>Local control page. Simulation starts by default. Hardware actions run asynchronously and never store passwords.</small></p>
<div class="grid">
<section><h2>Status</h2><div id="status">Loading…</div><p><a id="fox" target="_blank" rel="noreferrer">Open hardware Foxglove websocket</a></p><p><a id="simfox" target="_blank" rel="noreferrer">Open simulation Foxglove websocket</a></p></section>
<section><h2>Simulation</h2><button onclick="action('/api/simulation/start')">Start simulation</button><button onclick="action('/api/simulation/stop')">Stop simulation</button></section>
<section><h2>Robot connection</h2>
<label>Rock64 host/IP <input id="host" placeholder="auto (recommended)"></label>
<label>SSH user <input id="user" value="rock64"></label>
<label>Connection <select id="mode"><option value="ssh">SSH tunnel (recommended)</option><option value="direct">Direct DDS</option></select></label>
<label>Discovery server <input id="discovery" placeholder="192.168.1.139:11811"></label>
<label>Rock64 login password <input id="sshpass" type="password" autocomplete="new-password"></label>
<label>Separate sudo password <input id="sudo" type="password" autocomplete="new-password" placeholder="leave blank if same"></label>
<button onclick="discoverRobot()">Auto-detect Rock64</button><button onclick="setupRobot()">Set up + start robot</button><button onclick="startRobot()">Start robot</button><button onclick="stopRobot()">Stop robot</button>
<small id="found"></small>
</section>
<section><h2>SSH setup</h2><p>Use <b>Set up + start robot</b> once. It discovers the Rock64 on this PC/phone hotspot, installs the generated SSH key using the login password, verifies key-only access, and starts the stack. The password is never saved.</p><details><summary>Manual fallback</summary><p>If password login is disabled on the Rock64, copy this public key to its account’s <code>~/.ssh/authorized_keys</code>:</p><pre id="key">Loading…</pre><button onclick="navigator.clipboard.writeText(document.getElementById('key').textContent)">Copy key</button></details></section>
<section class="danger"><h2>Firmware</h2><p class="warn">Use only with the robot secured and the required ST-Link/ESP32 hardware connected.</p><label>Type FLASH to confirm <input id="confirm"></label><label><input id="esp32" type="checkbox" checked> Flash ESP32 camera too</label><button onclick="flashRobot()">Flash and verify firmware</button></section>
<section class="wide"><h2>Activity</h2><pre id="logs">Loading…</pre></section>
</div>
<script>
async function getStatus(){let r=await fetch('/api/status');let s=await r.json();
 document.getElementById('status').innerHTML=`Simulation: <b>${s.simulation}</b><br>Rock64: <b>${s.robot}</b><br>Action: <b>${s.job.state}</b> ${s.job.message||''}`;
 document.getElementById('fox').href=s.foxglove_url; document.getElementById('simfox').href=s.simulation_foxglove_url; document.getElementById('key').textContent=s.public_key; document.getElementById('logs').textContent=s.logs.join('\n');
 document.getElementById('host').value=s.config.robot_host === 'auto' ? '' : s.config.robot_host; document.getElementById('user').value=s.config.robot_user; document.getElementById('mode').value=s.config.connection_mode; document.getElementById('discovery').value=s.config.discovery_server; document.getElementById('found').textContent=s.discovered_hosts.length ? `Found SSH devices: ${s.discovered_hosts.join(', ')}` : '';
}
async function action(url,body={}){let r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});let j=await r.json();if(!r.ok)alert(j.error||'Action failed');getStatus();}
function fields(){return {robot_host:document.getElementById('host').value || 'auto',robot_user:document.getElementById('user').value,connection_mode:document.getElementById('mode').value,discovery_server:document.getElementById('discovery').value,sudo_password:document.getElementById('sudo').value}}
function discoverRobot(){action('/api/robot/discover',fields())}
async function setupRobot(){await action('/api/robot/setup',{...fields(),ssh_password:document.getElementById('sshpass').value});document.getElementById('sshpass').value=''}
function startRobot(){action('/api/robot/start',fields())} function stopRobot(){action('/api/robot/stop',{sudo_password:document.getElementById('sudo').value})}
function flashRobot(){action('/api/robot/flash',{confirmation:document.getElementById('confirm').value,flash_esp32:document.getElementById('esp32').checked,sudo_password:document.getElementById('sudo').value})}
getStatus();setInterval(getStatus,4000);
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        return

    def send_json(self, data: Any, status: int = 200) -> None:
        payload = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 32_000:
            raise ValueError("request body too large")
        raw = self.rfile.read(length) if length else b"{}"
        value = json.loads(raw.decode("utf-8"))
        return value if isinstance(value, dict) else {}

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/":
            payload = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        elif self.path == "/api/status":
            try:
                self.send_json(status())
            except Exception as exc:  # noqa: BLE001
                self.send_json({"error": str(exc)}, 500)
        elif self.path == "/api/logs":
            with LOCK:
                self.send_json({"logs": list(LOGS)})
        else:
            self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        try:
            payload = self.body()
            if self.path == "/api/simulation/start":
                launch_job("start simulation", start_simulation, payload)
            elif self.path == "/api/simulation/stop":
                launch_job("stop simulation", stop_simulation, payload)
            elif self.path == "/api/robot/start":
                launch_job("start robot", start_robot, payload)
            elif self.path == "/api/robot/setup":
                launch_job("automatic SSH setup and start", setup_ssh_and_start, payload)
            elif self.path == "/api/ssh/setup":
                launch_job("automatic SSH setup", setup_ssh, payload)
            elif self.path == "/api/robot/discover":
                launch_job("discover Rock64", discover_robot, payload)
            elif self.path == "/api/robot/stop":
                launch_job("stop robot", stop_robot, payload)
            elif self.path == "/api/robot/flash":
                launch_job("flash firmware", flash_robot, payload)
            else:
                self.send_error(404)
                return
            self.send_json({"accepted": True}, 202)
        except Exception as exc:  # noqa: BLE001
            self.send_json({"error": str(exc)}, 400)


def main() -> None:
    ensure_key()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    log(f"Operator page available at http://127.0.0.1:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop_process(TUNNEL)
        stop_process(DIRECT_DASHBOARD)
        server.server_close()


if __name__ == "__main__":
    main()
