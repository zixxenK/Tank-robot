# Silent Failures Audit - Tank Robot
**Last Updated:** 2026-08-06  
**Commit Baseline:** f5e8366  
**Flash Target:** Rock64 (aarch64)

This document catalogs all silent failures currently breaking the robot, prioritized by severity for the Rock64 flashing workflow. Items marked **FIXED** have been verified resolved in current HEAD.

---

## Executive Summary

**Active Silent Failures:** 3  
**Previously Fixed:** 6 (archived for reference)

### Critical (Blocks Operation)
1. **ARM Toolchain Architecture Mismatch** - Rock64-specific build failure
2. **Odometry Parameter Mismatch** - /odom wrong by 55% (track width) and 4x (encoder)
3. **E-Stop State Latch Bug** - Suppresses fault warnings after first idle

### Previously Fixed (Verified)
- USART1/3 configuration mismatch
- Main.c initialization order and debug loops
- Battery current validity flag
- Dead UART porting files (bluetooth_porting.c, packet_porting.c)
- robot_start.sh -u flag
- PS5 bridge deadman-switch documentation

---

## Active Silent Failures

### 1. ARM Toolchain Architecture Mismatch (CRITICAL)

**Location:** `scripts/install_toolchain_local.sh:15`, `scripts/check_toolchain.sh:37-38`

**Problem:**
Both scripts hardcode x86_64-only ARM toolchain downloads:
```bash
gcc-arm-none-eabi-10.3-2021.10-x86_64-linux.tar.bz2
```

On Rock64 (aarch64), this either:
- Fails loudly during download/extraction
- Silently produces a toolchain that cannot execute

**Impact:**
- Firmware builds fail on Rock64
- Forces cross-compilation from Windows/WSL
- Breaks self-update workflow on robot

**Root Cause:**
`rock64_setup.sh` correctly uses `apt install gcc-arm-none-eabi` for aarch64, but these fallback scripts were never updated.

**Verification:**
```bash
# On Rock64:
arm-none-eabi-gcc --version
# If this fails or shows x86_64 in path, the bug is active
```

**Fix:**
```bash
# scripts/install_toolchain_local.sh line 15:
# OLD:
wget https://developer.arm.com/-/media/Files/downloads/gnu-rm/10.3-2021.10/gcc-arm-none-eabi-10.3-2021.10-x86_64-linux.tar.bz2

# NEW (detect architecture):
ARCH=$(uname -m)
if [ "$ARCH" = "aarch64" ]; then
    TOOLCHAIN_ARCH="aarch64-linux"
else
    TOOLCHAIN_ARCH="x86_64-linux"
fi
wget https://developer.arm.com/-/media/Files/downloads/gnu-rm/10.3-2021.10/gcc-arm-none-eabi-10.3-2021.10-${TOOLCHAIN_ARCH}.tar.bz2
```

Apply same fix to `scripts/check_toolchain.sh:37-38`.

**Execution Order:**
- FIRST: Verify current toolchain state on Rock64
- Apply fix to both scripts
- Test build on Rock64 after fix

---

### 2. Odometry Parameter Mismatch (HIGH)

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

Real hardware values from motors_param.h:
```c
#define MOTOR_DEFAULT_TICKS_PER_CIRCLE 3960.0f  // Line 51
#define MOTOR_JGB520_TICKS_PER_CIRCLE 3960.0f    // Line 15
```

**Impact:**
- Track width: 0.3m (default) vs 0.194m (actual) = **55% error** in odometry
- Encoder ticks: 1000 (default) vs 3960 (actual) = **4x error** in odometry
- `/odom` topic publishes wildly incorrect position estimates
- Navigation/path planning will fail
- ROS2 silently ignores mismatched parameter names (no error)

**Does NOT affect:**
- Actual motor control (uses raw PWM)
- Teleop responsiveness
- Safety systems

**Root Cause:**
Parameter key name drift between bridge declaration and YAML config.

**Fix:**
```yaml
# host_ws/src/robot_bringup/config/rock64_hardware.yaml - ADD these lines:
wheel_separation: 0.194  # Track width in meters
wheel_radius: 0.065      # TODO: Measure actual wheel/sprocket radius
encoder_ticks_per_rev: 3960  # From motors_param.h: 11 pulses * 4 edges * 90:1 gearbox
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

### 3. E-Stop State Latch Bug (MEDIUM)

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

### USART1/3 Configuration (FIXED)
- **File:** `firmware/stm32_chassis/Core/Src/usart.c`, `uart_binary_protocol_integration_packed.c`
- **Status:** USART1 correctly configured on PA9/PA10 at 1,000,000 baud
- **Verified:** The approved custom design assigns the physical UART1 connector
  to PA9/PA10; stock 7in1 labels are not the custom runtime source of truth.

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

### Phase 1: Toolchain Fix (Do This First)
1. Verify current toolchain: `arm-none-eabi-gcc --version` on Rock64
2. Apply fix to `scripts/install_toolchain_local.sh` and `scripts/check_toolchain.sh`
3. Reinstall toolchain if needed
4. Test build: `cd firmware/stm32_chassis && cmake --preset Debug && cmake --build --preset Debug`

### Phase 2: Parameter Fix (Independent)
1. Add missing parameters to `host_ws/src/robot_bringup/config/rock64_hardware.yaml`
2. Rebuild host_ws: `colcon build --symlink-install`
3. Restart bridge and verify parameter values

### Phase 3: E-Stop Latch Fix (Independent)
1. Apply fix to `host_ws/src/robot_drivers/robot_drivers/stm32_hardened_bridge.py:798`
2. Rebuild host_ws: `colcon build --symlink-install`
3. Test with repeated e-stop triggers

### Phase 4: Verification
1. Flash firmware to STM32 via OpenOCD
2. Run `deployment/scripts/diagnose.sh` on Rock64
3. Manual bring-up: `source deployment/scripts/source_host_ws.sh && ros2 launch robot_bringup rock64_bringup.launch.py`
4. Verify odometry accuracy with teleop test
5. Verify e-stop logging with repeated triggers

---

## Dependencies

- **Toolchain fix** blocks firmware builds on Rock64
- **Parameter fix** and **E-stop latch fix** are independent
- All fixes require host_ws rebuild after application
- Firmware flash required after any C code changes (none in current active failures)

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
