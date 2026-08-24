# HC-SR04 production build path

This is the single production path for one HC-SR04 on the Hiwonder ROS Robot
Controller V1.2 (`STM32F407VET6`). Do not use the Rock64 GPIO header, an I2C
socket, an SBUS socket, or an Arduino for this sensor.

## 1. Physical wiring

Power the robot down before wiring. The four HC-SR04 wires are split across the
two three-pin headers because the active firmware uses one signal header for
each signal:

| HC-SR04 wire | Controller connection | Active MCU pin |
|---|---|---|
| `VCC` | `J4` `+5V` | 5 V rail |
| `GND` | `J4` `GND` (or `-`) | Common ground |
| `TRIG` | `J4` signal (`S`) | `PC8` |
| `ECHO` | `J2` signal (`S`) | `PA12` |

Use the printed `S`, `+5V`, and `GND` markings on the board; do not infer the
three-pin order from wire colours. Keep `J1/PA11` reserved for the SG90. Do
not connect the sensor to `PC10/PC11`: those are not the active ultrasonic
header signals in this build.

The HC-SR04 is powered at 5 V and normally returns a 5 V `ECHO` pulse. The
STM32F407 pins are documented as 5 V tolerant, but the complete controller
board input path has not been electrically verified. The safe first build uses
a divider or level shifter on `ECHO` (for example, 10 kohm from sensor `ECHO`
to `PA12` and 20 kohm from `PA12` to GND). Never apply an unverified 5 V signal to
the controller. A separate Arduino shield is not required.

## 2. Firmware path

The checked-in STM32 image owns the complete timing path:

1. `PC8` is a push-pull output and emits a 10 us trigger pulse.
2. `PA12` is a rising/falling-edge EXTI input on `EXTI12`.
3. `EXTI15_10_IRQHandler` dispatches the `PA12` edge to `hc_sr04.c`.
4. `DWT->CYCCNT` measures the high pulse in microseconds without blocking the
   motor loop.
5. Readings from 2 cm through 4 m are accepted; missing or out-of-range echoes
   are marked invalid.

The pin ownership is defined together in these files and must stay aligned:

- `firmware/stm32_chassis/RosRobotControllerM4.ioc`
- `firmware/stm32_chassis/stm32pinscustom.csv`
- `firmware/stm32_chassis/Core/Inc/main.h`
- `firmware/stm32_chassis/Core/Src/gpio.c`
- `firmware/stm32_chassis/Core/Src/stm32f4xx_it.c`
- `firmware/stm32_chassis/Hiwonder/System/hc_sr04.c`

## 3. STM32-to-Rock64-to-ROS path

The sensor does not appear as a USB device. Its data follows the existing
motor-controller transport:

```text
HC-SR04 -> STM32 PC8/PA12 -> USART1 PA9/PA10
         -> WCH USB-UART -> Rock64 /dev/rock64_stm32
         -> stm32_hardened_bridge -> /ultrasonic/range
```

The STM32 sends function `0x14` ultrasonic telemetry. The Rock64 bridge
publishes `sensor_msgs/Range` on `/ultrasonic/range` with frame
`ultrasonic_link`, `min_range=0.02`, and `max_range=4.0`. Invalid readings are
published as `NaN`. Function `0x15` carries trigger/rising-edge/falling-edge
counters, which are included in `/stm32/diagnostics`.

## 4. Exact build, flash, and test order

Do not connect the sensor until the current image is flashed.

From Windows, with the Rock64 connected and its ST-Link attached:

```powershell
powershell -File scripts/reflash_rock64.ps1 -Port UART1
```

When already logged into the Rock64, the equivalent release command is:

```bash
bash deployment/scripts/rock64_update_and_flash.sh
```

That workflow builds the Rock64 ROS workspace and STM32 Release image, flashes
and verifies the STM32 through ST-Link, starts the image, and runs the safe
UART proof. After it passes:

1. Power down and wire the sensor exactly as in section 1.
2. Keep the tracks raised and motor power disabled.
3. Start the hardware graph with the standard Rock64 bringup.
4. Observe the range and diagnostics:

   ```bash
   ros2 topic echo /ultrasonic/range
   ros2 topic echo /stm32/diagnostics
   ```

5. Put a flat target at a known distance. Accept the result only when
   `/ultrasonic/range` reports a plausible value and diagnostics show valid
   cycles with rising and falling edge counts increasing.

If diagnostics stay at `waiting_rise`, check sensor power, common ground, the
`J2` `S` contact, and the `ECHO` level-protection path. If trigger counts do not
increase, check the flashed image and the `J4` `S` contact. A ROS topic alone
cannot prove that the sensor is electrically wired correctly.

## 5. What is not part of this path

- No Arduino, Arduino shield, or second microcontroller.
- No direct Rock64 GPIO timing.
- No `PC10/PC11` sensor assignment.
- No reuse of `J1/PA11` for the ultrasonic signal.
- No operation with an older firmware image that treats `J2/PA12` or `J4/PC8`
  as servo outputs.
