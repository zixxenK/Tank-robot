# Tank Robot — Architecture Audit & Remediation Plan v2

**Scope:** `zixxenK/Tank-robot`, commit `ce53c71` (current `main`, 2026-07-30).
**Method:** Every claim below was checked directly against source in this commit
(file + line references included). This supersedes `ARCHITECTURE_AUDIT_SUMMARY.md`
and `deployment/REMEDIATION_PLAN.md`, both of which describe a version of the
firmware that predates several changes already made on `main`.

---

## 0. Do this today (not architectural — a real credential leak)

`firmware/esp32_sensors/include/secrets.h` is committed to git and contains a
**live WiFi SSID and password in plaintext**. This repo is public. That password
is public. `.gitignore` covers `*.env` but was never extended to this header, so
every firmware rebuild keeps re-committing it.

- Rotate the WiFi password now, independent of anything else in this doc.
- Move the real value into a gitignored `secrets.h` generated from a
  `secrets.h.example` template (same pattern already used for
  `deployment/systemd/systemd_config.conf.example`).
- Treat the current value as burned — scrubbing it from history (`git filter-repo`
  or BFG) only matters if you also rotate it; rotating without scrubbing is the
  higher-value action if you only do one.

---

## 1. The core finding: the STM32↔ROS2 control path does not work end-to-end

This is the thing every other item in this document is downstream of. The old
audit's four "critical issues" (udev rule, USART2 baud rate, protocol
translation, missing systemd config) have mostly been addressed already — see
§4 — but a **deeper, unfixed break** sits underneath them, and it's why the
robot likely still doesn't drive even after applying the old plan.

### 1.1 The host talks to USART2. The firmware's live control loop listens on USART3.

- `deployment/docs/deployment_guide.md`, `ROS_INTEGRATION_GUIDE.md`, and the
  udev rule (`host_ws/src/ros_robot_controller/scripts/99-ttyACM0.rules`) all
  agree: `/dev/rock64_stm32` is the CH340 USB-serial adapter, and every doc
  says it maps to **USART2 @ 115200**. `firmware/stm32_chassis/Core/Src/usart.c:108`
  confirms `huart2.Init.BaudRate = 115200` — this part *is* correctly fixed.
- But the binary protocol handler that is actually compiled and running
  (`Hiwonder/System/uart_binary_protocol_integration_packed.c:73-79`) calls
  `binary_protocol_init_packed(&protocol_ctx, &huart3, ...)` — **USART3**, at
  **1,000,000 baud** (`usart.c:137`), with its own DMA streams and a TIM2
  watchdog.
- `StartDefaultTask()` in `Core/Src/freertos.c:461-484` runs
  `binary_protocol_main_task()` in a tight 100 Hz loop — this is the only
  motor-command path that is actually active in firmware — and it is 100%
  USART3-based.
- USART2 itself: `HAL_UART_Init(&huart2)` runs and its IRQ is wired
  (`stm32f4xx_it.c:327`, `HAL_UART_IRQHandler(&huart2)`), but **nothing in the
  compiled firmware ever arms an RX request on it** (no
  `HAL_UART_Receive_IT`, no `HAL_UARTEx_ReceiveToIdle_DMA` for `huart2` exists
  in any file that's actually part of the build — the only callers of those
  are in `uart_ros_cmd.c` / `uart_ros_integration.c` / `bluetooth_porting.c`,
  none of which are compiled, see §1.2). Bytes arriving over
  `/dev/rock64_stm32` are simply never read by the MCU.
- Net effect: **every byte any host bridge sends is discarded**, regardless of
  which bridge or protocol you pick, because it arrives on a UART peripheral
  the firmware isn't listening to.

There's no evidence anywhere in the deployment tooling of a second serial
device or GPIO-UART path that would correspond to USART3 — grepped
`deployment/`, `host_ws/src/robot_bringup/`, `docs/`, nothing references
1 Mbaud or a second `/dev/tty*`. So this doesn't look like "USART3 is for a
different, undocumented physical link" — it looks like the binary-protocol
integration was pointed at the wrong `huart*` handle and nobody's driven the
robot far enough over UART to notice.

**Fix — pick one:**
- **(Recommended, smallest change):** In
  `uart_binary_protocol_integration_packed.c:74`, change `&huart3` → `&huart2`,
  and repoint its DMA streams to USART2's (`hdma_usart2_rx`/`tx` — confirm these
  are enabled in `usart.c`/`dma.c`; USART2 may currently only be interrupt-driven,
  not DMA-driven, which is its own follow-up). Re-verify the TIM2 watchdog isn't
  claimed elsewhere.
- **(Alternative):** If USART3 was deliberately chosen for a future dedicated
  GPIO-UART link to the Rock64 (bypassing the USB dongle for lower latency /
  higher throughput at 1 Mbaud), document that intent explicitly, wire the
  physical connection, and update `deployment/docs/deployment_guide.md` +
  `create_udev_rules.sh` + `rock64_hardware.yaml` to point the ROS bridges at
  the new device instead of `/dev/rock64_stm32`.

Either way, **this is the first thing to fix and verify with a logic analyzer
or scope before touching anything else** — everything downstream (protocol
choice, baud rate, launch args) is moot until bytes physically arrive where
firmware is listening.

### 1.2 Firmware has seven UART-protocol source files; three build, four are dead weight

`firmware/stm32_chassis/Hiwonder/System/` contains:

| File | In `CMakeLists.txt` build? | Status |
|---|---|---|
| `uart_binary_protocol_packed.c/h` | ✅ Yes (`CMakeLists.txt:66`) | Active — see §1.1 |
| `uart_binary_protocol_integration_packed.c/h` | ✅ Yes (`CMakeLists.txt:67`) | Active — see §1.1 |
| `uart_binary_protocol.c/h` (unpacked) | ❌ No | Dead code |
| `uart_binary_protocol_integration.c/h` (unpacked) | ❌ No | Dead code |
| `uart_ros_bridge.c/h` | ❌ No | Dead code, and even if wired in, its TX calls are commented out (`uart_ros_bridge.c:189,200,213`) |
| `uart_ros_cmd.c/h` | ❌ No | Dead code |
| `uart_ros_integration.c/h` | ❌ No | Dead code |

`app.c:120-121` even has the intended init calls commented out
(`// uart_ros_cmd_init();`), and `freertos.c:435`
(`// app_taskHandle = osThreadNew(app_task_entry, ...)`) confirms `app.c`'s
whole task — along with the USB-gamepad-driven `tankblack_control()` control
loop and `gampad_handle.c` — is quarantined and never runs. This is good; it's
explicitly labeled "BLOAT QUARANTINE" in the CMake file and looks intentional.
The problem is just that the *dead* files are still sitting in the tree
looking like plausible protocol implementations, which is exactly how the
original audit's "add `uart_ros_bridge.c`" recommendation ended up shipped but
inert. **Recommendation:** delete the four dead files (or move to
`firmware/stm32_chassis/_deprecated/`) so nobody reads them as ground truth
again.

### 1.3 Even after §1.1 is fixed, the default launch config still won't match the firmware

`host_ws/src/robot_bringup/launch/rock64_bringup.launch.py:186-206` launches
`stm32_serial_bridge` (the **ASCII** `<motor_id,direction,speed>\n` bridge) by
default (`use_binary_bridge` defaults to `"false"`). But the only protocol the
firmware actually parses is the binary `0xAA 0x55 ...` frame format. To match
what firmware speaks, you need `use_binary_bridge:=true`, which nothing in
`robot_start.sh` or `systemd_config.conf.example` currently sets.

### 1.4 The launch file silently re-breaks the baud rate it just fixed

`rock64_bringup.launch.py:198-206` and `:208-224` (both `serial_bridge_node`
and `binary_bridge_node`) pass:

```python
parameters=[
    LaunchConfiguration("hardware_config"),
    {"serial_port": LaunchConfiguration("serial_port")},
    {"baud_rate": 9600},   # <-- hardcoded
],
```

`rock64_hardware.yaml` correctly sets `baud_rate: 115200`, but in ROS 2 launch,
when a node is given multiple parameter sources in a list, **later entries
override earlier ones for the same key**. The hardcoded `9600` dict comes
after the yaml, so it wins — every launch, every time, via the exact
`robot_start.sh` → `rock64_bringup.launch.py` path systemd uses. This is the
kind of bug that's invisible in a diff and only shows up as "garbage on the
wire" at 3am. **Fix:** delete the `{"baud_rate": 9600}` line from both nodes
and let the yaml's `115200` (or, cleaner, a `LaunchConfiguration` argument)
be the single source of truth.

### 1.5 The best bridge on the host side isn't wired to anything

`host_ws/src/robot_drivers/robot_drivers/stm32_hardened_bridge.py` (34 KB,
CRC-8, reconnect logic, telemetry parsing, heartbeat/timeout failsafe — and
its constants match the firmware's `uart_binary_protocol_packed.h` exactly)
has:
- No `console_scripts` entry in `setup.py` (`host_ws/src/robot_drivers/setup.py:24-31`
  registers `chassis_bridge`, `stm32_serial_bridge`, `stm32_binary_bridge`,
  `esp32_camera_bridge`, `motor_bringup_test`, `stm32_selftest_cli`,
  `telemetry_markers` — not `stm32_hardened_bridge`).
- No `Node(...)` entry in `rock64_bringup.launch.py`.

It has its own test file (`test_stm32_hardened_bridge.py`) and is clearly the
most mature bridge in the repo, but you currently cannot even `ros2 run` it.
Given it's the one whose protocol constants actually match firmware, **this,
not `stm32_binary_bridge.py`, should become the default binary bridge** once
§1.1–§1.4 are fixed. `ranger_base_node.py` and `chassis_bridge.py` are in a
similar half-wired state and worth auditing for the same reason before you
build on top of any of them.

### 1.6 Function-code collision between the Python binary bridge and firmware

`stm32_binary_bridge.py:51` defines `FUNC_EMERGENCY_STOP = 0x11` and calls
`self._send_frame(FUNC_EMERGENCY_STOP)` at line 613 to e-stop. Firmware's
`uart_binary_protocol_packed.h` defines `0x11` as `FUNC_BATTERY` (a
device→host telemetry code, not a command). Firmware's dispatcher
(`uart_binary_protocol_packed.c:255-280`) has no `case` for `0x11` as an
inbound function — it falls through to `default: // Unknown function code -
ignore`. **A deliberate top-level e-stop sent this way is silently dropped.**
The firmware *does* have a working e-stop path
(`FUNC_MOTOR` / `MOTOR_SUBCMD_EMERGENCY_STOP`, handled correctly at
`uart_binary_protocol_packed.c:271-275`) — `stm32_binary_bridge.py` just isn't
using it for its dedicated stop call. `stm32_hardened_bridge.py`'s constants
line up with firmware's enum, so check whether it has the same bug before
promoting it (§1.5).

The firmware's timeout-based failsafe (`binary_protocol_check_timeouts()`,
`uart_binary_protocol_packed.c:314-322`) is a working independent safety net —
loss of comms still stops the robot — so this bug is "explicit stop command
ignored," not "runaway with no failsafe at all." Still worth fixing before you
rely on it.

---

## 2. `agent_core` / safety gateway is fully disconnected

`host_ws/src/agent_core/agent_core/safety_gateway.py` implements a 50 Hz
watchdog that clamps `/agent/cmd_vel_proposed` → `/ranger/cmd_vel_safe`, drops
commands on stale heartbeat, and zeroes velocity on `/safety/e_stop`. It's a
reasonable design. But:

- It is **not launched anywhere** — no `Node(...)` for `safety_gateway` exists
  in any `launch.py` in the repo.
- Nothing in the repo subscribes to its output topic, `/ranger/cmd_vel_safe`
  (grepped every `.py`/`.launch.py`/`.xml` — zero hits outside `agent_core`
  itself and `deployment/safety_config.yaml`). Even if you launched it today,
  its clamped commands would go nowhere.
- `deployment/safety_config.yaml` reads like the design spec for this node
  (topics, `heartbeat_timeout_ms: 100`, kinematic limits) but
  `safety_gateway.py` never loads it — it hardcodes its own defaults via
  `declare_parameter(..., 0.5)`, i.e. a **500 ms** heartbeat timeout, 5x looser
  than the yaml's 100 ms. Two sources of truth, silently disagreeing, and
  neither is read by the other.

If there's an actual plan to let an AI agent drive this robot, this is the
component that's supposed to keep that safe, and right now it's decorative.
Treat wiring this in — launch entry, topic consumer on the hardware side, and
making it actually load `safety_config.yaml` — as a prerequisite for any
agent-driven motion, not a nice-to-have.

---

## 3. Structural debt that will keep costing you time

### 3.1 Three ROS 2 workspaces, two of them silently drifting

`host_ws` (canonical), `ros2_ws` (README-documented "migration source,"
intentionally kept as a fallback), and `robot_ws` (a from-scratch bootstrap
scaffold via `ros2 pkg create`, seemingly unrelated to the other two's
history). This tri-workspace layout is documented and the *intent* is
reasonable, but the fallback isn't inert:

- `robot_start.sh`'s `resolve_host_ws()` falls back to `ros2_ws` if
  `host_ws/src` doesn't exist for any reason (bad checkout, partial rsync,
  typo'd `HOST_WS_PATH`).
- `ros2_ws/src/robot_drivers/robot_drivers/` is missing `chassis_bridge.py`,
  `stm32_hardened_bridge.py`, `ranger_base_node.py`, `telemetry_markers.py`,
  `minimal_test.py`, `simple_validate.py`, `validate_bridge.py`, and its
  `stm32_serial_bridge.py`/`motor_bringup_test.py` have **diverged in content**
  from `host_ws`'s versions (confirmed via `diff`, not just filename
  differences).
- Net effect: a silent fallback to `ros2_ws` doesn't fail loudly — it boots a
  materially older, less-capable bridge stack, and everything looks "fine" in
  `systemctl status` while behaving differently than whatever you last tested
  on `host_ws`.

**Fix:** either make `resolve_host_ws()` fail loudly instead of silently
falling back (an unexpected fallback to legacy code on a mobile robot should
be a startup error, not a quiet substitution), or delete `ros2_ws` now that
`host_ws` is canonical and keep the migration script + a git tag for history
instead of a live fallback path.

### 3.2 `robot_ws` is unclear in purpose

It's a bootstrap scaffold that runs `ros2 pkg create` fresh — not a copy of
`host_ws`/`ros2_ws` history. Nothing else in the repo references it. If it's
meant to be a from-scratch rebuild recipe for a corrupted workspace, say so in
the top-level `README.md` (it's currently only documented in its own nested
`robot_ws/README.md`, easy to miss); if it's stale exploration, remove it —
three workspace directories in one repo is already one more than most
contributors will track correctly.

### 3.3 ROS distro mismatch between dev container and deployment target

`.devcontainer/devcontainer.json:3` uses `osrf/ros:jazzy-desktop`, and
`install-toolchain.sh:25` installs `ros-jazzy-rmw-fastrtps-cpp`. Every
deployment script, the top-level `README.md`, and `REMEDIATION_PLAN.md`
target **Humble** (`source /opt/ros/humble/setup.bash`, `apt install
ros-humble-desktop`, etc.). Jazzy and Humble aren't ABI/API-identical
(`launch` API and some `rclpy` behavior differs across those releases).
Anyone developing inside the provided devcontainer is testing against a
different ROS distro than what ships to the Rock64. Pin the devcontainer to
`humble-desktop` unless there's a specific reason to develop against Jazzy,
in which case document why and what's been verified compatible.

### 3.4 `deployment/safety_config.yaml` and other config files nobody loads

Beyond §2's specific case, it's worth a pass to check which YAML/config files
in `deployment/` are actually loaded by any node vs. describing an intended
design that was never wired up — they're easy to mistake for the current
behavior when reading the repo top-down.

### 3.5 Nine of twenty-one deployment scripts are ad-hoc patches

`deployment/scripts/fix_bridge_config.sh`, `fix_controller_detection.sh`,
`fix_input_permissions.sh`, `fix_ps5_device_path.sh`,
`fix_ros2_environment.sh`, `quick_fix_device_access.sh`,
`quick_node_check.sh`, `quick_ps5_test.sh`, `quick_rebuild.sh` — a `fix_*`/
`quick_*` script is a reasonable thing to have once or twice, but nine out of
twenty-one deployment scripts in that naming pattern suggests recurring
firefighting (particularly around PS5-controller device detection — four
separate scripts touch that one problem) rather than a config that's
converged. Once §1 is actually fixed and verified, it's worth folding the
durable fixes from these into `rock64_setup.sh`/the udev rules/systemd unit
directly, and archiving the rest — a fresh Rock64 flash shouldn't need nine
manual patch scripts to reach a working state.

### 3.6 `systemd_config.conf` doesn't exist until someone creates it

`deployment/systemd/rock64-robot.service` has
`EnvironmentFile=/opt/rock64-robot/deployment/systemd/systemd_config.conf`,
but only `systemd_config.conf.example` is committed (by design — it has a
per-device IP). First boot on a freshly cloned repo will have systemd fail to
start with a missing-EnvironmentFile error unless `apply_systemd.sh` (which
does create it) has been run first. This is fine as long as `apply_systemd.sh`
is a hard prerequisite step in the setup docs — confirm it's not skippable in
`rock64_setup.sh`'s happy path.

### 3.7 Minor code-quality flags worth a look, lower priority

- `robot_start.sh:9` — `set -eo pipefail` with a comment
  `# Removed -u to allow undefined variables`. That's turning off a real
  protection because something broke, rather than fixing the underlying unbound
  variable. Worth revisiting once the boot path is stable — `-u` would have
  caught a class of the config-drift bugs in this document earlier.
- `ps5_ros_bridge.py` has no explicit deadman-switch parameter — it relies on
  `stm32_serial_bridge`'s own `heartbeat_timeout`/`cmd_timeout` to stop the
  robot if teleop input stops arriving. That's probably fine, but it means the
  "stop on release" behavior lives one hop away from the teleop node itself;
  worth a comment in `ps5_ros_bridge.py` pointing at where that safety net
  actually lives so it isn't "rediscovered" later.

---

## 4. What's already fixed since the last audit (don't redo this work)

Credit where due — comparing the old `ARCHITECTURE_AUDIT_SUMMARY.md` against
current `main`:

- ✅ Udev rule now targets the correct device and creates
  `/dev/rock64_stm32` correctly (`99-ttyACM0.rules`, matches in both
  workspaces).
- ✅ `usart.c:108` — USART2 is at 115200, matching docs (it's just the wrong
  peripheral for the active protocol handler — §1.1 — not the wrong baud rate
  anymore).
- ✅ `rock64_hardware.yaml` has the correct `baud_rate: 115200` (it's overridden
  at launch time — §1.4 — but the source of truth itself is correct).
- ✅ `robot_start.sh` resolves the active workspace and passes real launch args
  instead of a bare `ros2 launch` call.
- ✅ `preflight_check.py` catches real config-consistency mistakes (conflicting
  mode flags, missing serial device) before nodes start — good pattern, worth
  extending (see §5).

---

## 5. Prioritized remediation plan

### Phase 0 — Security (today, ~15 min)
1. Rotate the WiFi password in `secrets.h`. Gitignore the real file; commit
   only `secrets.h.example`.

### Phase 1 — Make the control path physically real (do this before anything else)
1. Confirm with a scope/logic analyzer which UART pins are actually wired
   from the CH340 dongle into the STM32, and which are wired (if any) from
   USART3.
2. Repoint `uart_binary_protocol_integration_packed.c:74` at `huart2` (or
   formally commit to a USART3 GPIO link and update every doc/script that
   currently references `/dev/rock64_stm32`/USART2 — pick one, don't leave
   both stories in the repo).
3. If moving to USART2: confirm DMA streams are available/enabled for it
   (`usart.c`/`dma.c`), or fall back to interrupt-driven RX if DMA channels
   are already claimed by USART3/other peripherals.
4. Delete the four dead UART-protocol files (§1.2) so the next person doesn't
   read them as current behavior.
5. Flash, then verify with `screen`/`picocom` at the *correct* baud that raw
   bytes sent from the host actually reach and are acknowledged by firmware,
   before layering ROS back on top.

### Phase 2 — Make the host side match firmware
1. Fix the `{"baud_rate": 9600}` override in `rock64_bringup.launch.py`
   (§1.4) for both `serial_bridge_node` and `binary_bridge_node`.
2. Register `stm32_hardened_bridge` as a console script in
   `host_ws/src/robot_drivers/setup.py` and add its `Node(...)` to
   `rock64_bringup.launch.py`, gated the same way `binary_bridge_node` is.
3. Fix the `FUNC_EMERGENCY_STOP` function-code collision (§1.6) — route
   through `FUNC_MOTOR` + `MOTOR_SUBCMD_EMERGENCY_STOP` instead of the
   colliding top-level `0x11`. Check whether `stm32_hardened_bridge.py` has
   the same issue before promoting it to default.
4. Once verified working, flip `use_binary_bridge` default to `"true"` (or
   retire the ASCII bridge entirely, since firmware never spoke it).

### Phase 3 — Wire the safety gateway in, or remove it
Pick one — don't leave it half-built:
- **Wire it in:** add `safety_gateway` to a launch file, make it actually load
  `deployment/safety_config.yaml` instead of hardcoded defaults, and make
  whichever bridge is canonical (§1.5) subscribe to `/ranger/cmd_vel_safe`
  when running in agent-driven mode.
- **Remove it:** if there's no near-term plan for agent-driven control, say so
  in the README and move `agent_core` to a clearly-marked `experimental/` or
  `future/` location so it doesn't read as "the safety layer that's protecting
  this robot right now."

### Phase 4 — Structural cleanup
1. Decide `ros2_ws`'s fate: hard-fail on fallback, or delete it (§3.1).
2. Document or remove `robot_ws` (§3.2).
3. Pin devcontainer to Humble, or document the Jazzy delta explicitly (§3.3).
4. Consolidate the nine `fix_*`/`quick_*` scripts' durable fixes into the base
   setup path; archive the rest (§3.5).

### Phase 5 — Verification you can automate
- Add a preflight check (extending the existing `preflight_check.py` pattern)
  that fails launch if the selected bridge's protocol doesn't match a
  firmware version/capability flag — e.g. have firmware report its active
  protocol + UART in its heartbeat/ACK frame, and have the bridge refuse to
  proceed silently if it doesn't get one back in N seconds, rather than
  running forever with zero effect.
- A simple host-side loopback test (send a known frame, assert the specific
  ACK/telemetry response) would have caught §1.1, §1.4, and §1.6 immediately
  and is worth keeping as a permanent CI/bench check, not just a one-time
  verification step.

---

## 6. Evidence index (file:line quick reference)

| Finding | Key files |
|---|---|
| USART2 vs USART3 mismatch | `Core/Src/usart.c:107-137`, `Hiwonder/System/uart_binary_protocol_integration_packed.c:73-79`, `Core/Src/freertos.c:461-484` |
| Dead UART protocol files | `firmware/stm32_chassis/CMakeLists.txt:52-158` (source list), `Hiwonder/System/app.c:120-121`, `Core/Src/freertos.c:417-438` |
| ASCII bridge default vs binary-only firmware | `host_ws/src/robot_bringup/launch/rock64_bringup.launch.py:60-72,186-206` |
| Launch-time baud override | `rock64_bringup.launch.py:198-224` vs `host_ws/src/robot_bringup/config/rock64_hardware.yaml` |
| Orphaned hardened bridge | `host_ws/src/robot_drivers/setup.py:24-31` vs `robot_drivers/stm32_hardened_bridge.py` |
| E-stop function-code collision | `robot_drivers/stm32_binary_bridge.py:51,613` vs `Hiwonder/System/uart_binary_protocol_packed.h:29-38`, `.c:255-280` |
| Disconnected safety gateway | `host_ws/src/agent_core/agent_core/safety_gateway.py`, `deployment/safety_config.yaml` — grep repo-wide for `cmd_vel_safe`/`safety_gateway` |
| Workspace drift | `diff -rq host_ws/src/robot_drivers ros2_ws/src/robot_drivers`, `deployment/scripts/robot_start.sh` `resolve_host_ws()` |
| ROS distro mismatch | `.devcontainer/devcontainer.json:3,34` vs `README.md`, `deployment/scripts/*.sh` |
| Secret leak | `firmware/esp32_sensors/include/secrets.h` |

---

*This document reflects a point-in-time code review, not a runtime test on
hardware. §1's physical-wiring hypothesis (USART2 vs USART3) should be
confirmed with a scope before code changes — it's possible there's a hardware
revision or wiring harness not represented in this repo that makes USART3
correct. Everything else here is confirmed purely from source, independent of
wiring.*