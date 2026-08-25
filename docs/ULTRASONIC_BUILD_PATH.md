# HC-SR04 controller-header build path

The supported ultrasonic sensor is the HC-SR04 connected directly to the
Hiwonder ROS Robot Controller V1.2. The controller exposes the required
`5V`, `GND`, `PC8`, and `PA12` contacts and the STM32F407 echo input is 5-V
tolerant. No external level shifter or voltage divider is used.

## Wiring

Use a keyed, labeled harness and the signal names printed on the board:

| HC-SR04 wire | Controller contact |
|---|---|
| VCC | `5V` |
| GND | `GND` |
| TRIG | `PC8` |
| ECHO | `PA12` |

Do not use `VIN`, the battery rail, `PC9`, or the Rock64 GPIO header. Verify
the labeled 5-V rail with a meter before first connection.

## Firmware and ROS path

```text
HC-SR04 -> PC8/PA12 -> STM32 -> USART1 -> Rock64
         -> stm32_hardened_bridge -> /ultrasonic/range
```

The STM32 emits a 10-us trigger pulse on `PC8`, measures the echo pulse on
`PA12` with EXTI12 and the DWT cycle counter, and rejects measurements outside
20--400 cm. Measurements use HC-SR04 protocol functions `0x17` and `0x18`;
the ROS topic remains `/ultrasonic/range`.

PB12 is left as a normal input because it shares EXTI12 with PA12. The IMU
driver polls I2C2, so this does not remove IMU samples from telemetry.

## Acceptance

With motor power disabled and the robot stationary:

```bash
ros2 topic echo /ultrasonic/range
ros2 topic echo /stm32/diagnostics
```

Confirm trigger activity and both echo edges with a scope or logic analyzer,
then test several known target distances. The HC-SR04 path remains outside
motor safety decisions until these checks pass.
