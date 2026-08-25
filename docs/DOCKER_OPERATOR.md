# Docker operator workflow

The supported clean-PC entry point is Windows 10/11 with Internet access and
local administrator permission. PowerShell downloads the bootstrapper, then
the bootstrapper installs Git, WSL2, and Docker Desktop when they are absent:

```powershell
irm https://raw.githubusercontent.com/zixxenK/Tank-robot/main/scripts/bootstrap_tankrobot.ps1 | iex
```

The bootstrapper resumes after a WSL-required restart, clones the latest
`main` branch under `%LOCALAPPDATA%\TankRobot\Tank-robot`, builds the ROS 2
Humble images, starts headless Gazebo, and opens:

```text
http://127.0.0.1:<selected-local-port>
```

The local operator page keeps simulation available when no Rock64 is on the
network. It also provides Start robot, Stop robot, firmware flashing, health,
logs, and the current Foxglove websocket link.

## Physical robot setup

The first physical start is automatic. In the operator page, leave the
Rock64 host blank (or use `auto`), confirm the SSH user (normally `rock64`),
enter the Rock64 login password, and press **Set up + start robot**. The
operator searches the PC/phone hotspot for `rock64.local` and common hotspot
subnets, installs its generated SSH key through the one-time password, and
verifies passwordless SSH. No key copying, `authorized_keys` editing, or IP
typing is required.

The login password is used only in memory during this action. It is never
stored in the Docker volume, command arguments, logs, or status response. If
the Rock64 uses a different sudo password, enter it in the separate sudo
field; otherwise leave that field blank. Future starts need the sudo password
only when the Rock64 requires it for deployment.

There is a manual public-key fallback in the page for Rock64 images that have
password authentication disabled. A completely untouched machine must expose
either password SSH for this one-time enrollment or an already-installed key;
software cannot authenticate to a machine when neither credential exists.

**Set up + start robot** synchronizes the current checkout, rebuilds the Rock64 ROS
workspace, applies the service configuration, starts the acquisition and PS5
teleoperation stack, and attaches Foxglove. It does not flash either
controller. The default SSH-tunnel connection avoids Docker Desktop DDS
multicast problems. Direct DDS is available when a discovery server or a
network configuration that supports ROS 2 discovery has been provided.

The Flash and verify firmware action is separate and requires typing `FLASH`.
Use it only with the robot secured and the required Rock64 ST-Link/ESP32
hardware connected. Firmware programming remains Rock64-owned.

## Compose commands

After the bootstrapper has installed Docker Desktop, the equivalent local
commands are:

```powershell
cd "$env:LOCALAPPDATA\TankRobot\Tank-robot"
docker compose -p tankrobot up -d --build
Start-Process http://127.0.0.1:28787
```

The operator page is bound to localhost. The simulation Foxglove endpoint is
`ws://127.0.0.1:28766` by default; the SSH hardware tunnel is
`ws://127.0.0.1:28765`; direct DDS hardware mode uses
`ws://127.0.0.1:28767` by default. The Windows bootstrapper probes and selects
free ports automatically.

Linux and macOS can use the same Compose commands after installing Docker
Engine/Desktop and Compose. Automatic operating-system prerequisite
installation is intentionally Windows-first.
