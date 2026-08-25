# Tank Robot operator guide

## Current milestone

The active robot path is:

```text
PS5 DualSense -> /cmd_vel -> safety_gateway -> /ranger/cmd_vel_safe
             -> stm32_hardened_bridge -> USART1/WCH -> STM32F407
ESP32 camera and USB camera -> ROS image topics -> PC/Foxglove (read-only)
```

The canonical PS5 map is
`host_ws/src/robot_control/config/control_map.yaml`:

- Left-stick vertical: signed forward/reverse throttle.
- Right-stick horizontal: steering, always live.
- R2: analog linear-throttle multiplier. Released R2 commands zero linear
  motion and acts as the brake; it does not disable steering.
- L2: analog drift/power-pivot modifier.
- L1/R1: precision/boost mode scaling.

The drift calculation is normalized and clamped as a pair. With `T` as signed
throttle after R2 multiplication, `S` as steering, and `D` as L2 pressure:

```text
V' = T * (1 - 0.9 * D * abs(S))
W' = S * (1 + 2.75 * D)
left  = V' + W'
right = V' - W'
```

The right track intentionally reverses during a full right power pivot. This
is a tracked-chassis pivot effect, not wheel-style slip simulation.

## Bring-up and acceptance

On the Rock64, run from the repository root:

```bash
bash scripts/hardware_acceptance.sh
```

The basic required gate is bridge, encoders, odometry, onboard controller IMU,
ESP32 camera, and USB camera. PS5 teleoperation is still started and remains
service-owned, but controller connection or operator input is not an
acceptance failure. The project runtime expects QMI8658 on the Hiwonder
controller, while Hiwonder's live product/hardware pages still say MPU6050.
Its firmware evidence reports
I2C2 (`PB10=SCL`, `PB11=SDA`), address, WHO_AM_I, sample count, and errors.

Securely raise both tracks before the independent motor proof:

```bash
bash scripts/hardware_acceptance.sh --tracks-raised
```

The runner always starts with the ROS e-stop asserted and stops both motors on
exit. Servo, Glowy ultrasonic, LiDAR, and battery are outside this basic
acceptance workflow and are neither launched nor reported by it. The IMU is
always required; there is no basic-profile bypass for it.

## Normal driving

After acceptance passes, start the persistent graph with the deployed service
or:

```bash
bash scripts/onecmd.sh
```

Keep the emergency-stop control available. The PS button asserts the latched
ROS e-stop and OPTIONS requests a clear; all commands still pass through the
safety gateway. The serial bridge retains finite-value checks, command
timeout, output clamping, STM32 watchdog, PID, and motor protection. Command
slew shaping is disabled for the teleop profile so L2 drift can reverse the
inside track; this does not bypass the timeout or e-stop chain.

## Cameras and Foxglove

The PC dashboard is read-only. Use
`deployment/pc/foxglove/tank_robot_readonly_layout.json` as a native Foxglove
layout import. It places the ESP32 and USB compressed image topics side by
side:

```text
/camera/image_raw/compressed       /camera/usb/image_raw/compressed
```

Connect to the endpoint printed by `deployment/pc/run_dashboard.ps1` or
`deployment/pc/run_dashboard.sh`. The dashboard does not publish movement
commands.

## LM Studio

LM Studio is a future-safe assistant running on the PC/WSL side. It can explain
diagnostics, produce review-only code proposals, or submit short bounded
proposals to the safety gateway. It never writes directly to motor hardware,
flashes firmware, or bypasses e-stop, command limits, heartbeat, or timeout.
See [LM_STUDIO_INTEGRATION.md](LM_STUDIO_INTEGRATION.md) for authenticated
startup.
