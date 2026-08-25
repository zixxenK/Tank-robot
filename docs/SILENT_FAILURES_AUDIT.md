# Silent-failure audit

**Status:** current checkout reviewed 2026-08-24

The operator workflow is [OPERATOR_GUIDE.md](OPERATOR_GUIDE.md). This file
records failure boundaries and the historical issues that must not be
reintroduced. The production wiring remains defined by
[SOURCE_OF_TRUTH_1_0.md](SOURCE_OF_TRUTH_1_0.md).

The complete board inventory and Hiwonder-source conflict record is
[HIWONDER_ROS_ROBOT_CONTROLLER_V1_2.md](HIWONDER_ROS_ROBOT_CONTROLLER_V1_2.md).

## Current failure boundaries

| Boundary | Fail-closed behavior | Evidence/check |
| --- | --- | --- |
| PS5 or keyboard input | `/cmd_vel` expires after the safety timeout | `/teleop/ps5_status`, `ros2 topic hz /cmd_vel` |
| LM Studio/autonomy | `/agent/cmd_vel_proposed` is rejected without a fresh `/agent/heartbeat` | `/safety/diagnostics` reports heartbeat stale |
| Safety gateway | E-stop, command timeout, finite checks, limits, and optional battery gate stop output | `/ranger/cmd_vel_safe`, `/safety/diagnostics` |
| STM32 serial bridge | Reconnect and command timeout issue a stop; only this node writes motor frames | `/stm32/diagnostics`, `/stm32/bridge_alive` |
| STM32 firmware | CRC/protocol validation, watchdog, PID, PWM, and motor protection remain authoritative | Firmware build plus raised-track proof |
| Onboard IMU identity | I2C2 probe/WHO_AM_I/read errors are reported instead of publishing a false-ready stream; QMI is not accepted from a label alone | `/stm32/imu`, onboard IMU diagnostic status |
| Cameras | Each bridge reports stale/unreachable input; camera data has no motor authority | `/camera/diagnostics`, `/camera/usb/diagnostics` |
| PC/WSL loss | The Rock64 safety and STM32 stop paths remain local | Stop test with the PC disconnected |

## Resolved issues that must stay resolved

### Canonical odometry and geometry

The historical parameter-name drift is fixed. The production bridge and track
conversion both load geometry from:

```text
host_ws/src/robot_control/config/control_map.yaml
```

That file owns `track_width_m=0.194`, `max_track_speed_mps=0.8`, and the shared
tracked-drive conversion. The hardware YAML intentionally does not duplicate
track geometry. Encoder scale remains the production `1980` ticks/output
revolution in the hardware parameters and firmware contract.

Do not add old `wheel_separation` or duplicate geometry keys to
`rock64_hardware.yaml` unless the ownership contract is deliberately changed
and all consumers/tests are updated together.

### Production UART

The only production motor transport is WCH `1a86:55d4` at
`/dev/rock64_stm32` -> physical UART1 -> STM32 USART1 PA9/PA10, 1,000,000 8N1.
USART3/PD8-PD9 is reference-board material only. ST-Link is programming/debug
only. The PC deployment path delegates flashing to the Rock64.

### E-stop and timeout visibility

The safety gateway owns ROS command arbitration and e-stop state. The
hardened bridge and STM32 firmware each retain independent command freshness
timeouts and emergency-stop behavior. Repeated e-stop and reconnect behavior
must remain observable in diagnostics; a successful motor stop alone is not
enough evidence.

### IMU ownership

The project uses a QMI8658 runtime assumption for the onboard sensor. Hiwonder's
current product/hardware text says MPU6050 while its program-analysis section
3.5 says QMI8658, so the part identity is not established by documentation
alone. The active firmware path is I2C2 on PB10/SCL and PB11/SDA at 400 kHz,
with address probing at `0x6A` and `0x6B`, `WHO_AM_I` register `0x00` expected
to return `0x05`, and one serialized telemetry owner to avoid FreeRTOS/I2C
races. PB12 remains the board's IMU interrupt input; the active wrapper uses
status polling so the UART protocol task remains the sole sample owner. A
failed IMU stage means inspect controller power, I2C2 wiring, probe/address,
the physical sensor marking, and firmware diagnostics before changing ROS topic
names.

## Deferred hardware

Servo, battery ADC calibration, Glowy ultrasonic, LiDAR, spare encoder
channels, terrain adaptation, navigation, perception, and autonomous
arbitration are future or optional upgrades. Their code and references may
remain in the repository, but they must not silently become part of the
current acceptance gate or create a second motor command path.

## Verification sequence

1. Run the offline contract suite and build the host workspace.
2. Build the STM32 image; flash only through the Rock64 release workflow.
3. Run `bash scripts/hardware_acceptance.sh` with tracks down for the
   non-motion drive/camera/IMU gate.
4. Run `--tracks-raised` only with both tracks physically secured when the
   independent motor proof is required.
5. Test e-stop, source timeout, serial reconnect, and firmware timeout before
   a floor test.

The active source of truth is the code, tests, and operator guide linked above;
the old audit recommendations to add duplicate odometry parameters or to
require optional accessories are obsolete.
