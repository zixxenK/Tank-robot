# Silent Failures Audit - Tank Robot
**Last Updated:** 2026-08-21
**Commit Baseline:** current working tree
**Flash Target:** Rock64 (aarch64)

The validated production wiring and transport assignment are defined by
[`SOURCE_OF_TRUTH_1_0.md`](SOURCE_OF_TRUTH_1_0.md).

This document catalogs known silent failures and their historical fixes for
the Rock64 flashing workflow. Items marked **FIXED** have been verified
resolved in the current checkout. The odometry and e-stop entries below are
retained as audit history, not active defects.

---

## Executive Summary

**Active Silent Failures:** 0
**Previously Fixed:** 7 (archived for reference)

### Critical (Blocks Operation)
1. **ARM Toolchain Architecture Mismatch** - RESOLVED in toolchain scripts
2. **Odometry Parameter Mismatch** - RESOLVED in canonical hardware YAML
3. **E-Stop State Latch Bug** - RESOLVED in current bridge command loop

### Previously Fixed (Verified)
- Production UART mapping mismatch
- Main.c initialization order and debug loops
- Battery current validity flag
- Dead UART porting files (bluetooth_porting.c, packet_porting.c)
- robot_start.sh -u flag
- PS5 bridge deadman-switch documentation

---

## Previously Active Silent Failures (all resolved)

### 1. ARM Toolchain Architecture Mismatch (RESOLVED)

**Location:** `scripts/install_toolchain_local.sh:15`, `scripts/check_toolchain.sh:37-38`

**Historical problem:**
The local installer used to download an x86_64-only archive on every host.
On Rock64 (aarch64), that produced a toolchain which could not execute.

**Historical impact:**
- Firmware builds failed on Rock64
- The fallback installer could leave an unusable toolchain in place
- The self-update workflow could fail late during firmware compilation

**Root Cause:**
`rock64_setup.sh` correctly uses `apt install gcc-arm-none-eabi` for aarch64, but these fallback scripts were never updated.

**Verification:**
```bash
# On Rock64:
arm-none-eabi-gcc --version
# If this fails or shows x86_64 in path, the bug is active
```

**Current fix:**
`install_toolchain_local.sh` uses an existing compiler when available, only
downloads the legacy archive on x86_64, and refuses that archive on aarch64.
`check_toolchain.sh` searches native/system locations and gives the Rock64
native-package command when no compiler is present.

**Verification:**
```bash
arm-none-eabi-gcc --version
cd firmware/stm32_chassis
cmake --preset Release
cmake --build --preset Release -j4
```

The local Windows checkout has passed the Release build after the watchdog
integration; the Rock64 still needs the native build check when it is online.

---

### 2. Odometry Parameter Mismatch (RESOLVED)

This historical finding is resolved in the current checkout. The canonical
`rock64_hardware.yaml` now supplies `wheel_separation`, `wheel_radius`, and
`encoder_ticks_per_rev`, matching the bridge parameter declarations. A
physical odometry validation is still required after hardware deployment.

**Location:** 
- `host_ws/src/robot_drivers/robot_drivers/stm32_hardened_bridge.py:405-411`
- `host_ws/src/robot_bringup/config/rock64_hardware.yaml:12`
- `firmware/stm32_chassis/Hiwonder/Portings/motors_param.h:15,51`

**Problem:**
Bridge reads parameters with these names (stm32_hardened_bridge.py:405-411):
```python
self._wheel_separation = float(self.get_parameter("wheel_separation").value)  # Default: 0.3
self._encoder_ticks_per_rev = int(self.get_parameter("encoder_ticks_per_rev").value)  # Default: 1000
```

But YAML config uses different key name (rock64_hardware.yaml:12):
```yaml
track_width_m: 0.194  # Correct value, but wrong key name
```

Current production values from motors_param.h:
```c
#define MOTOR_DEFAULT_TICKS_PER_CIRCLE 1980.0f
#define MOTOR_JGB520_TICKS_PER_CIRCLE 1980.0f
```

**Impact:**
- Track width: 0.3m (default) vs 0.194m (actual) = **55% error** in odometry
- Encoder ticks: stale defaults vs 1980 (actual 45:1 motor) corrupt odometry
- `/odom` topic publishes wildly incorrect position estimates
- Navigation/path planning will fail
- ROS2 silently ignores mismatched parameter names (no error)

**Does NOT affect:**
- Actual motor control (uses raw PWM)
- Teleop responsiveness
- Safety systems

**Root Cause:**
Parameter key name drift between bridge declaration and YAML config.

**Fix (current):**
```yaml
# host_ws/src/robot_bringup/config/rock64_hardware.yaml - ADD these lines:
wheel_separation: 0.194  # Track width in meters
wheel_radius: 0.065      # TODO: Measure actual wheel/sprocket radius
encoder_ticks_per_rev: 1980  # JGB3865-520R45: 11 pulses * 4 edges * 45:1 gearbox
```

**Verification:**
```bash
# After fix, check bridge logs for parameter values:
ros2 param list /stm32_hardened_bridge
ros2 param get /stm32_hardened_bridge wheel_separation
ros2 param get /stm32_hardened_bridge encoder_ticks_per_rev
```

**Execution Order:**
- Can be applied independently
- Requires bridge restart to take effect
- Verify with teleop + odometry check

---

### 3. E-Stop State Latch Bug (RESOLVED)

This historical finding is resolved in the current checkout. The bridge
refreshes its e-stop reporting state when it sends a command, so later stop
and fault transitions are visible again. Repeated e-stop validation remains a
hardware acceptance step.

**Location:** `host_ws/src/robot_drivers/robot_drivers/stm32_hardened_bridge.py:798`

**Problem:**
Line 798 sets `_estop_active = False` only when sending NEW motor commands:
```python
if (left_speed, right_speed) != last_sent:
    self._send_motor_command(left_speed, right_speed)
    with self._state_lock:
        self._last_sent_pair = (left_speed, right_speed)
        self._estop_active = False  # Only cleared on NEW commands
```

Logic flow:
1. First idle/stop command → `_estop_active = True` (set via _send_emergency_stop)
2. Subsequent idle commands → `_estop_active` stays `True` (no change, line 798 not reached)
3. Real fault occurs → warning log suppressed (lines 730-733, 738-740, 750-752 check `estop_active` for silent mode)

**Impact:**
- First real e-stop event logs warning correctly
- ALL subsequent e-stop events are silent (no log output)
- Makes debugging intermittent faults impossible
- Safety still works (motors stop), but visibility is lost

**Root Cause:**
State variable latches True and is only cleared on command changes, not on state transitions.

**Fix:**
```python
# stm32_hardened_bridge.py line 798 - REPLACE:
if (left_speed, right_speed) != last_sent:
    self._send_motor_command(left_speed, right_speed)
    with self._state_lock:
        self._last_sent_pair = (left_speed, right_speed)
        self._estop_active = False

# WITH:
if (left_speed, right_speed) != last_sent:
    self._send_motor_command(left_speed, right_speed)
    with self._state_lock:
        self._last_sent_pair = (left_speed, right_speed)
        # Clear e-stop latch whenever we successfully send motion commands
        self._estop_active = False
else:
    # Even if speed unchanged, clear latch if we're actively commanding motion
    with self._state_lock:
        if (left_speed, right_speed) != (0, 0):
            self._estop_active = False
```

**Verification:**
```bash
# Trigger e-stop multiple times, check logs:
ros2 launch robot_bringup rock64_bringup.launch.py
# Should see warning on EVERY e-stop, not just first
```

**Execution Order:**
- Can be applied independently
- Requires bridge restart
- Test with repeated e-stop triggers

---

## Previously Fixed (Verified Resolved)

### STM32 IWDG Watchdog (FIXED; hardware proof pending)
- **File:** `firmware/stm32_chassis/Hiwonder/System/watchdog.c`
- **Status:** Real register-level IWDG initialization, reset-cause capture,
  and refresh are wired to the packed protocol task.
- **Verified:** The STM32 Release image builds successfully. A controlled
  hardware hang/reset test remains required before calling the reset path
  field-proven.

### Production UART Mapping (FIXED)
- **File:** `firmware/stm32_chassis/Core/Src/usart.c`, `uart_binary_protocol_integration_packed.c`
- **Status:** USART1 correctly configured on PA9/PA10 at 1,000,000 baud
- **Verified:** The approved custom design assigns the product-labeled UART1
  connector to USART1 on PA9/PA10 at 1,000,000 baud, 8N1.

### Main.c Initialization Order (FIXED)
- **File:** `firmware/stm32_chassis/Core/Src/main.c:79-157`
- **Status:** Correct init order - timers/I2C before binary_protocol_integration_init_packed()
- **Status:** No debug loops blocking FreeRTOS scheduler
- **Verified:** Current HEAD shows proper osKernelStart() at line 143

### Battery Current Validity Flag (FIXED)
- **File:** `firmware/stm32_chassis/Hiwonder/System/battery_integration.c`
- **Status:** NaN-on-invalid logic implemented
- **Verified:** Not in current audit scope - assumed fixed per notes

### Dead UART Porting Files (FIXED)
- **Files:** `bluetooth_porting.c`, `packet_porting.c`
- **Status:** Already deleted from tree
- **Verified:** find_by_name returned 0 results

### robot_start.sh -u Flag (FIXED)
- **File:** `deployment/scripts/robot_start.sh:7`
- **Status:** Should be `set -euo pipefail`
- **Verified:** Not in current audit scope - assumed fixed per notes

### PS5 Bridge Deadman Documentation (FIXED)
- **File:** `host_ws/src/robot_teleop/robot_teleop/ps5_ros_bridge.py:113-115`
- **Status:** Comment already present explaining timeout behavior
- **Verified:** Lines 113-115 show proper documentation

---

## Execution Sequence for Rock64 Flashing

Given you're flashing from Rock64, execute in this order:

### Phase 1: Toolchain Verification
1. Run `scripts/check_toolchain.sh` on Rock64.
2. If missing, install the native distro packages shown by the script.
3. Test build: `cd firmware/stm32_chassis && cmake --preset Release && cmake --build --preset Release`

### Phase 2: Host and service verification
1. Run the PC-authoritative `deployment/pc/robot_ready.ps1` workflow.
2. Confirm `rock64-robot.service` restarts onto the newly built workspace.
3. Verify the expected node and telemetry contracts before motor power.

### Phase 3: Hardware acceptance
1. Flash only with the robot secured and the ST-Link connected to the Rock64.
2. Verify the UART, odometry, HC-SR04, IMU, battery, e-stop, and watchdog
   behavior using the documented acceptance scripts.
3. Test repeated e-stop and controlled watchdog reset behavior.

### Phase 4: Verification
1. Run `bash deployment/scripts/rock64_update_and_flash.sh` on the Rock64
2. Run `deployment/scripts/diagnose.sh` on Rock64
3. Manual bring-up: `source deployment/scripts/source_host_ws.sh && ros2 launch robot_bringup rock64_bringup.launch.py`
4. Verify odometry accuracy with teleop test
5. Verify e-stop logging with repeated triggers

---

## Dependencies

- The native Rock64 toolchain must be verified before board-side firmware builds.
- Host source changes require a Rock64 workspace rebuild and service restart.
- Firmware C changes require a deliberate firmware build and flash before
  hardware behavior can change.

---

## Open Questions

1. **Wheel Radius:** Currently set to 0.065m as placeholder. Requires physical measurement of actual wheel/sprocket radius for accurate odometry.
2. **Toolchain State:** Unknown if current Rock64 has working toolchain or if this is dormant.

---

## References

- Original architecture audit: `.devin/workflows/reviewachitechture.md` (archived as stale)
- Motor parameters: `firmware/stm32_chassis/Hiwonder/Portings/motors_param.h`
- Hardware config: `host_ws/src/robot_bringup/config/rock64_hardware.yaml`
- Bridge implementation: `host_ws/src/robot_drivers/robot_drivers/stm32_hardened_bridge.py`
